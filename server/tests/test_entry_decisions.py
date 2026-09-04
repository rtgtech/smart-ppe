import json
import unittest
import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.routes.entry import REQUIRED, _evaluate
from app.models import Alert, AttendanceLog, AuditLog, Base, ComplianceLog, Department, Device, Gate, GateEvent, Mine, PpeDetection, PpeItem, Worker, WorkerPpe


class EntryDecisionTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        mine = Mine(name="Mine", location="Test", status="ACTIVE")
        self.db.add(mine)
        self.db.flush()
        department = Department(mine_id=mine.mine_id, name="Safety")
        gate = Gate(mine_id=mine.mine_id, name="Gate", location="Entry", latitude=1, longitude=2, status="ACTIVE")
        self.db.add_all([department, gate])
        self.db.flush()
        self.device = Device(gate_id=gate.gate_id, device_type="AI_CAMERA", serial_number="TEST-CAM", status="ONLINE")
        self.worker = Worker(employee_code="WORKER1", name="Worker One", department_id=department.department_id, status="ACTIVE")
        self.db.add_all([self.device, self.worker])
        self.db.flush()
        self.codes = {}
        for name in REQUIRED:
            item = PpeItem(name=name, is_mandatory=True)
            self.db.add(item)
            self.db.flush()
            code = str(uuid.uuid4())
            self.codes[name] = code
            self.db.add(WorkerPpe(worker_ppe_id=code, worker_id=self.worker.worker_id, ppe_id=item.ppe_id, status="ACTIVE"))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def frame(self, identity="MATCH", qrs=None, visual_state="POSITIVE", track_id=7, person_id="WORKER1"):
        return {
            "at": datetime.now(timezone.utc).isoformat(),
            "identity": {"state": identity, "person_id": person_id if identity == "MATCH" else None, "confidence": .92},
            "multiple": identity == "MULTIPLE", "quality_valid": True, "framing_valid": True,
            "luminance": 100, "sharpness": 150,
            "visual": {
                name: {
                    "state": visual_state,
                    "confidence": .9 if visual_state == "POSITIVE" else None,
                    "bbox": [[1, 1, 2, 2]] if visual_state == "POSITIVE" else None,
                    "track_id": track_id,
                    "roi": [[0, 0, 3, 3]],
                    "association_score": .8 if visual_state == "POSITIVE" else None,
                    "worn_state": "YES" if visual_state == "POSITIVE" else "NO" if visual_state == "NEGATIVE" else "UNKNOWN",
                }
                for name in REQUIRED
            },
            "qr_codes": list(qrs or []),
        }

    def event(self, frames):
        event = GateEvent(
            event_id=str(uuid.uuid4()), gate_id=self.device.gate_id, device_id=self.device.device_id,
            gate_latitude=1, gate_longitude=2, edge_timestamp=datetime.now(timezone.utc),
            lifecycle="ACTIVE", phase="IDENTITY", sync_status="SYNCED",
            evidence_json=json.dumps({"frames": frames, "qr_max_counts": {}, "qr_confirmed": {}, "qr_failures": {}}),
        )
        self.db.add(event)
        self.db.commit()
        return event

    def test_allowed_is_atomic_and_idempotent(self):
        event = self.event([self.frame(qrs=self.codes.values()) for _ in range(5)])
        self.assertTrue(_evaluate(self.db, event, force=True))
        self.db.commit()
        self.assertEqual(event.verdict, "ALLOWED")
        self.assertEqual(self.db.query(ComplianceLog).count(), 1)
        self.assertEqual(self.db.query(AttendanceLog).count(), 1)
        self.assertEqual(self.db.query(PpeDetection).count(), 3)
        self.assertEqual(self.db.query(Alert).count(), 0)
        self.assertEqual(self.db.query(AuditLog).count(), 6)
        _evaluate(self.db, event, force=True)
        self.db.commit()
        self.assertEqual(self.db.query(ComplianceLog).count(), 1)
        self.assertEqual(self.db.query(AttendanceLog).count(), 1)
        self.assertEqual(self.db.query(AuditLog).count(), 6)

    def test_qr_is_not_required_for_known_worker(self):
        event = self.event([self.frame() for _ in range(5)])
        _evaluate(self.db, event, force=True)
        self.db.commit()
        self.assertEqual(event.verdict, "ALLOWED")
        self.assertFalse(any("QR" in reason for reason in json.loads(event.reasons_json)))
        self.assertEqual(self.db.query(Alert).count(), 0)
        self.assertEqual(self.db.query(AttendanceLog).count(), 1)

    def test_unknown_identity_holds_without_worker_log(self):
        event = self.event([self.frame(identity="UNKNOWN") for _ in range(5)])
        _evaluate(self.db, event, force=True)
        self.db.commit()
        self.assertEqual(event.verdict, "HOLD")
        self.assertIsNone(event.worker_id)
        self.assertEqual(self.db.query(ComplianceLog).count(), 0)
        self.assertEqual(self.db.query(Alert).one().alert_type, "GATE_IDENTITY_HOLD")

    def test_anatomical_assignment_is_persisted_for_ai_evidence(self):
        event = self.event([self.frame(qrs=self.codes.values()) for _ in range(5)])
        _evaluate(self.db, event, force=True)
        self.db.commit()
        detections = self.db.query(PpeDetection).filter(PpeDetection.detection_source == "AI").all()
        self.assertEqual(len(detections), 3)
        self.assertTrue(all(row.assignment_result == "YES" for row in detections))
        stored = json.loads(detections[0].bounding_box)
        self.assertEqual(stored["track_id"], 7)
        self.assertEqual(stored["association_score"], .8)

    def test_live_flow_locks_identity_before_collecting_ppe(self):
        event = self.event([self.frame() for _ in range(3)])
        self.assertFalse(_evaluate(self.db, event))
        self.assertEqual(event.phase, "EVIDENCE")
        self.assertEqual(event.worker_id, self.worker.worker_id)
        state = json.loads(event.evidence_json)
        self.assertEqual(state["frames"], [])
        self.assertIsNotNone(state["evidence_deadline"])
        self.assertEqual(state["summary"]["identity"]["state"], "CONFIRMED")

        state["frames"] = [self.frame() for _ in range(3)]
        event.evidence_json = json.dumps(state)
        self.assertTrue(_evaluate(self.db, event))
        self.db.commit()
        self.assertEqual(event.verdict, "ALLOWED")

    def test_ppe_stage_rejects_a_changed_identity(self):
        event = self.event([self.frame() for _ in range(3)])
        self.assertFalse(_evaluate(self.db, event))
        other = Worker(
            employee_code="WORKER2", name="Worker Two",
            department_id=self.worker.department_id, status="ACTIVE",
        )
        self.db.add(other)
        self.db.commit()
        state = json.loads(event.evidence_json)
        state["frames"] = [self.frame(person_id="WORKER2") for _ in range(3)]
        event.evidence_json = json.dumps(state)
        self.assertTrue(_evaluate(self.db, event))
        self.db.commit()
        self.assertEqual(event.verdict, "HOLD")
        self.assertEqual(event.worker_id, self.worker.worker_id)
        self.assertIn("IDENTITY_CHANGED", json.loads(event.reasons_json))

    def test_temporal_votes_do_not_mix_different_tracks(self):
        frames = [self.frame(track_id=7) for _ in range(2)]
        frames.extend(self.frame(track_id=8) for _ in range(2))
        frames.append(self.frame(visual_state="UNKNOWN", track_id=None))
        event = self.event(frames)
        _evaluate(self.db, event, force=True)
        self.db.commit()
        self.assertEqual(event.verdict, "HOLD")

    def test_previously_confirmed_worker_hold_keeps_compliance_audit(self):
        event = self.event([self.frame(identity="NONE") for _ in range(5)])
        event.worker_id = self.worker.worker_id
        event.phase = "EVIDENCE"
        self.db.commit()
        _evaluate(self.db, event, force=True)
        self.db.commit()
        self.assertEqual(event.verdict, "HOLD")
        self.assertEqual(self.db.query(ComplianceLog).one().final_verdict, "HOLD")
        self.assertEqual(self.db.query(AttendanceLog).count(), 0)

    def test_ppe_catalog_rejects_noncanonical_names(self):
        self.db.add(PpeItem(name="Gloves", is_mandatory=True))
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()


if __name__ == "__main__":
    unittest.main()
