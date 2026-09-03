import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import numpy as np
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.routes.workers import delete_worker
from app.models import (
    Alert,
    AttendanceLog,
    Base,
    ComplianceLog,
    Department,
    Gate,
    Mine,
    Notification,
    PpeDetection,
    PpeItem,
    Report,
    SafetyScore,
    Worker,
    WorkerPpe,
)
from app.services.face_recognition import FaceRegistry


class WorkerDeletionTest(unittest.IsolatedAsyncioTestCase):
    async def test_delete_removes_worker_relations_and_face_profile(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, _record):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()
        now = datetime.now(timezone.utc)

        mine = Mine(name="Test Mine", location="Test", status="ACTIVE")
        session.add(mine)
        session.flush()
        department = Department(mine_id=mine.mine_id, name="Test Department")
        gate = Gate(mine_id=mine.mine_id, name="Test Gate", location="Test", status="ACTIVE")
        ppe = PpeItem(name="Test Helmet", is_mandatory=True)
        session.add_all([department, gate, ppe])
        session.flush()
        worker = Worker(employee_code="DELETE_TEST", name="Delete Test", department_id=department.department_id)
        session.add(worker)
        session.flush()
        log = ComplianceLog(
            worker_id=worker.worker_id,
            gate_id=gate.gate_id,
            entry_time=now,
            overall_status="COMPLIANT",
            compliance_score=100,
            confidence_score=95,
            sync_status="SYNCED",
        )
        attendance = AttendanceLog(worker_id=worker.worker_id, gate_id=gate.gate_id, entry_time=now, status="INSIDE")
        session.add_all([log, attendance])
        session.flush()
        alert = Alert(
            log_id=log.log_id,
            worker_id=worker.worker_id,
            alert_type="TEST",
            severity="INFO",
            message="Test alert",
            status="ACTIVE",
        )
        session.add_all([
            WorkerPpe(worker_id=worker.worker_id, ppe_id=ppe.ppe_id, status="ACTIVE"),
            SafetyScore(worker_id=worker.worker_id, score=100, risk_level="LOW", violation_count=0, compliance_rate=100),
            PpeDetection(log_id=log.log_id, ppe_id=ppe.ppe_id, detected=True, confidence_score=95, detection_source="AI"),
            Report(report_type="WORKER_WISE", period_start=now.date(), period_end=now.date(), generated_by=worker.worker_id),
            alert,
        ])
        session.flush()
        session.add(Notification(alert_id=alert.alert_id, recipient_id=worker.worker_id, channel="APP", message="Test", status="SENT"))
        session.commit()

        with tempfile.TemporaryDirectory() as directory:
            registry = FaceRegistry(Path(directory) / "faces.json")
            registry.create("DELETE_TEST", "Delete Test", np.array([1.0, 0.0], dtype=np.float32))
            with patch("app.api.v1.routes.workers.require_face_services", return_value=(object(), registry)):
                response = await delete_worker(worker.worker_id, session)

            self.assertEqual(response.status, "DELETED")
            self.assertEqual(registry.count(), 0)

        for model in (Worker, WorkerPpe, SafetyScore, ComplianceLog, PpeDetection, AttendanceLog, Alert, Notification):
            self.assertEqual(session.query(model).count(), 0, model.__name__)
        report = session.query(Report).one()
        self.assertIsNone(report.generated_by)
        session.close()


if __name__ == "__main__":
    unittest.main()
