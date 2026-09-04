import json
import unittest
import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.routes.entry import REQUIRED, _evaluate
from app.models import Alert, AttendanceLog, Base, ComplianceLog, Department, Device, Gate, GateEvent, Mine, PpeDetection, PpeItem, Worker, WorkerPpe


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

    def frame(self, identity="MATCH", qrs=None, visual_state="POSITIVE"):
        return {
            "at": datetime.now(timezone.utc).isoformat(),
            "identity": {"state": identity, "person_id": "WORKER1" if identity == "MATCH" else None, "confidence": .92},
            "multiple": identity == "MULTIPLE", "quality_valid": True, "framing_valid": True,
            "luminance": 100, "sharpness": 150,
            "visual": {name: {"state": visual_state, "confidence": .9 if visual_state == "POSITIVE" else None, "bbox": [1, 1, 2, 2] if visual_state == "POSITIVE" else None} for name in REQUIRED},
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
        self.assertEqual(self.db.query(PpeDetection).count(), 6)
        self.assertEqual(self.db.query(Alert).count(), 0)
        _evaluate(self.db, event, force=True)
        self.db.commit()
        self.assertEqual(self.db.query(ComplianceLog).count(), 1)
        self.assertEqual(self.db.query(AttendanceLog).count(), 1)

    def test_missing_qr_denies_known_worker(self):
        event = self.event([self.frame() for _ in range(5)])
        _evaluate(self.db, event, force=True)
        self.db.commit()
        self.assertEqual(event.verdict, "DENIED")
        self.assertTrue(any(reason.endswith("QR_MISSING") for reason in json.loads(event.reasons_json)))
        self.assertEqual(self.db.query(Alert).one().severity, "CRITICAL")
        self.assertEqual(self.db.query(AttendanceLog).count(), 0)

    def test_unknown_identity_holds_without_worker_log(self):
        event = self.event([self.frame(identity="UNKNOWN") for _ in range(5)])
        _evaluate(self.db, event, force=True)
        self.db.commit()
        self.assertEqual(event.verdict, "HOLD")
        self.assertIsNone(event.worker_id)
        self.assertEqual(self.db.query(ComplianceLog).count(), 0)
        self.assertEqual(self.db.query(Alert).one().alert_type, "GATE_IDENTITY_HOLD")

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


if __name__ == "__main__":
    unittest.main()
