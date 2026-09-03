import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import numpy as np
from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.routes.workers import create_worker_with_face, delete_worker
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
from app.services.face_recognition import FaceRegistry, FaceServiceError


class RejectingFaceEngine:
    def enrollment_embedding(self, _captures):
        raise FaceServiceError("Capture 2 is invalid: no face was detected; exactly one is required.")


class AcceptingFaceEngine:
    def enrollment_embedding(self, _captures):
        return np.array([1.0, 0.0], dtype=np.float32)


class WorkerDeletionTest(unittest.IsolatedAsyncioTestCase):
    async def test_registry_write_failure_does_not_leave_duplicate_in_memory(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = FaceRegistry(Path(directory) / "faces.json")
            with (
                patch.object(registry, "_save", side_effect=FaceServiceError("Could not save face registry")),
                self.assertRaises(FaceServiceError),
            ):
                registry.create("WRITE_FAIL", "Write Failure", np.array([1.0, 0.0], dtype=np.float32))
            self.assertEqual(registry.count(), 0)

    async def test_successful_face_capture_creates_worker_and_profile_together(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()
        mine = Mine(name="Test Mine", location="Test", status="ACTIVE")
        session.add(mine)
        session.flush()
        department = Department(mine_id=mine.mine_id, name="Test Department")
        session.add(department)
        session.commit()
        payload = json.dumps({
            "employee_code": "FACE_OK",
            "name": "Face Success",
            "department_id": department.department_id,
            "status": "ACTIVE",
        })

        with tempfile.TemporaryDirectory() as directory:
            registry = FaceRegistry(Path(directory) / "faces.json")
            with (
                patch("app.api.v1.routes.workers.require_face_services", return_value=(AcceptingFaceEngine(), registry)),
                patch("app.api.v1.routes.workers.read_registration_images", new=AsyncMock(return_value=[object()] * 5)),
            ):
                response = await create_worker_with_face(payload, [object()] * 5, session)

            self.assertEqual(response.employee_code, "FACE_OK")
            self.assertEqual(registry.count(), 1)
            self.assertEqual(session.query(Worker).count(), 1)
        session.close()

    async def test_failed_face_capture_does_not_insert_worker(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()
        mine = Mine(name="Test Mine", location="Test", status="ACTIVE")
        session.add(mine)
        session.flush()
        department = Department(mine_id=mine.mine_id, name="Test Department")
        session.add(department)
        session.commit()

        payload = json.dumps({
            "employee_code": "FACE_FAIL",
            "name": "Face Failure",
            "department_id": department.department_id,
            "status": "ACTIVE",
        })
        with tempfile.TemporaryDirectory() as directory:
            registry = FaceRegistry(Path(directory) / "faces.json")
            with (
                patch("app.api.v1.routes.workers.require_face_services", return_value=(RejectingFaceEngine(), registry)),
                patch("app.api.v1.routes.workers.read_registration_images", new=AsyncMock(return_value=[object()] * 5)),
                self.assertRaises(HTTPException) as caught,
            ):
                await create_worker_with_face(payload, [object()] * 5, session)

            self.assertEqual(caught.exception.status_code, 422)
            self.assertEqual(registry.count(), 0)
            self.assertEqual(session.query(Worker).count(), 0)
        session.close()

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
            with patch("app.api.v1.routes.workers.require_face_registry", return_value=registry):
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
