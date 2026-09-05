import unittest
import uuid
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.routes.assistant_queries import resolve_worker, worker_attendance, worker_safety_summary
from app.models import AuditLog, AttendanceLog, Base, ComplianceLog, Department, Device, Gate, GateEvent, Mine, PpeDetection, PpeItem, Worker
from app.services.entry_persistence import entry_alert_details, persist_entry_session
from app.services.entry_pipeline import EntrySession


class AssistantReadinessTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        mine = Mine(name="Test Mine", location="Test", status="ACTIVE")
        self.db.add(mine)
        self.db.flush()
        department = Department(mine_id=mine.mine_id, name="Mining")
        gate = Gate(mine_id=mine.mine_id, name="Gate 01", location="Entry", latitude=1, longitude=1, status="ACTIVE")
        self.db.add_all([department, gate])
        self.db.flush()
        self.worker = Worker(employee_code="WORKER1", name="Worker One", department_id=department.department_id, status="ACTIVE")
        self.db.add_all([
            self.worker,
            Device(gate_id=gate.gate_id, device_type="AI_CAMERA", serial_number="AI-CAM-G01", status="ONLINE"),
            PpeItem(name="Helmet", is_mandatory=True),
            PpeItem(name="Vest", is_mandatory=True),
            PpeItem(name="Shoes", is_mandatory=True),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_finalized_scan_is_idempotently_persisted_and_queryable(self):
        session = EntrySession(str(uuid.uuid4()))
        face = [{"recognized": True, "person_id": "WORKER1", "name": "Worker One", "similarity": .93}]
        person = [{
            "helmet": "YES", "helmet_confidence": .91,
            "vest": "YES", "vest_confidence": .92,
            "boots": "YES", "boots_confidence": .94,
        }]
        session.add_identity(face, True)
        for _ in range(3):
            session.add_ppe(person, face, True)

        persist_entry_session(self.db, session)
        persist_entry_session(self.db, session)

        self.assertTrue(session.persisted)
        self.assertEqual(self.db.query(GateEvent).count(), 1)
        self.assertEqual(self.db.query(ComplianceLog).count(), 1)
        self.assertEqual(self.db.query(PpeDetection).count(), 3)
        self.assertEqual(self.db.query(AttendanceLog).count(), 1)
        self.assertEqual(self.db.query(AuditLog).count(), 1)
        self.assertEqual(resolve_worker("worker1", False, self.db)["status"], "RESOLVED")
        self.assertEqual(len(worker_attendance(self.worker.worker_id, None, None, 20, False, self.db)["records"]), 1)
        self.assertEqual(worker_safety_summary(self.worker.worker_id, 30, False, self.db)["score"], 100.0)

    def test_ppe_alert_identifies_worker_location_and_missing_item(self):
        alert_type, message = entry_alert_details(
            SimpleNamespace(reasons=["HELMET_NOT_WORN"]),
            SimpleNamespace(name="Ravi Kumar"),
            SimpleNamespace(name="Gate 02", location="Zone B"),
        )
        self.assertEqual(alert_type, "PPE_VIOLATION")
        self.assertEqual(
            message,
            "Ravi Kumar entered Zone B without a safety helmet. "
            "Missing required PPE: safety helmet.",
        )

    def test_unidentified_alert_includes_location_and_exact_reason(self):
        alert_type, message = entry_alert_details(
            SimpleNamespace(reasons=["IDENTITY_NOT_CONFIRMED"]),
            None,
            SimpleNamespace(name="Gate 02", location="Zone B"),
        )
        self.assertEqual(alert_type, "IDENTITY_VIOLATION")
        self.assertEqual(
            message,
            "Unidentified person detected at Zone B. Exact reason: identity not confirmed.",
        )

    def test_ppe_alert_uses_recognized_name_when_worker_row_is_unlinked(self):
        alert_type, message = entry_alert_details(
            SimpleNamespace(
                reasons=["VEST_NOT_WORN"],
                worker={"name": "Registry Worker"},
            ),
            None,
            SimpleNamespace(name="Gate 02", location="Zone B"),
        )
        self.assertEqual(alert_type, "PPE_VIOLATION")
        self.assertIn("Registry Worker entered Zone B", message)
        self.assertIn("safety vest", message)


if __name__ == "__main__":
    unittest.main()
