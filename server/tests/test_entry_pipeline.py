import unittest
import uuid
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.routes.entry import router
from app.services.entry_pipeline import EntrySession, SessionStore
from app.services.entry_pipeline import entry_sessions


def face(person_id="WORKER1"):
    return [{"recognized": True, "person_id": person_id, "name": "Worker One", "similarity": .9}]


def person(helmet="YES"):
    row = {}
    for item in ("glove", "goggles", "helmet", "mask", "shoes"):
        row[item] = helmet if item == "helmet" else "YES"
        row[f"{item}_confidence"] = .9
    return [row]


class EntryPipelineTest(unittest.TestCase):
    def identified(self):
        session = EntrySession("scan-1")
        session.add_identity(face(), True)
        self.assertEqual(session.phase, "EVIDENCE")
        return session

    def test_stable_identity_then_ppe_allows_entry_without_persistence(self):
        session = self.identified()
        for _ in range(3):
            session.add_ppe(person(), face(), True)
        result = session.result()
        self.assertEqual(result["verdict"], "ALLOWED")
        self.assertFalse(result["persisted"])
        self.assertEqual(result["storage"], "TRANSIENT_MEMORY")

    def test_three_missing_observations_deny_entry(self):
        session = self.identified()
        for _ in range(3):
            session.add_ppe(person("NO"), face(), True)
        self.assertEqual(session.verdict, "DENIED")
        self.assertIn("HELMET_NOT_WORN", session.reasons)

    def test_recognized_face_advances_even_when_quality_gate_is_low(self):
        session = EntrySession("scan-low-quality")
        session.add_identity(face(), False)
        self.assertEqual(session.phase, "EVIDENCE")
        self.assertEqual(session.worker["name"], "Worker One")

    def test_identity_change_holds_entry(self):
        session = self.identified()
        for _ in range(3):
            session.add_ppe(person(), face("WORKER2"), True)
        self.assertEqual(session.verdict, "HOLD")

    def test_discard_removes_transient_session(self):
        store = SessionStore()
        store.create("scan-1")
        self.assertTrue(store.discard("scan-1"))
        self.assertIsNone(store.get("scan-1"))

    def test_websocket_streams_metadata_and_annotated_frames(self):
        app = FastAPI()
        app.include_router(router)
        client, session_id = TestClient(app), str(uuid.uuid4())
        identified = (b"identity-jpeg", face(), {"valid": True}, 5.0)
        compliant = (b"ppe-jpeg", [], person(), face(), {"valid": True}, {"ppe_ms": 5.0})
        with (
            patch("app.api.v1.routes.entry.identity_frame", return_value=identified),
            patch("app.api.v1.routes.entry.ppe_frame", return_value=compliant),
        ):
            created = client.post("/entry/attempts", headers={"Idempotency-Key": session_id}).json()
            self.assertFalse(created["persisted"])
            with client.websocket_connect(f"/entry/attempts/{session_id}/stream") as stream:
                stream.receive_json()
                for _ in range(4):
                    stream.send_bytes(b"frame")
                    metadata = stream.receive_json()
                    stream.receive_bytes()
                self.assertEqual(metadata["entry"]["verdict"], "ALLOWED")
                self.assertEqual(stream.receive_json()["type"], "session_complete")
        entry_sessions.discard(session_id)


if __name__ == "__main__":
    unittest.main()
