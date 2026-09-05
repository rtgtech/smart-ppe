import unittest
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.main import app
from app.models import Base, Department, Mine, Worker
from app.schemas.voice import VoiceSessionStart
from app.services.voice_agent import live_config
from app.services.voice_tools import fetch_recent_workers, fetch_worker_names


class VoiceAgentTest(unittest.TestCase):
    def test_live_session_only_registers_worker_listing_tools(self):
        config = live_config()
        self.assertEqual(config.speech_config.language_code, "en-IN")
        names = {
            declaration.name
            for tool in config.tools
            for declaration in tool.function_declarations
        }
        self.assertEqual(names, {"list_worker_names", "list_recent_workers"})

    def test_worker_name_tool_returns_all_workers_in_name_order(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        try:
            mine = Mine(name="Test Mine", location="Test", status="ACTIVE")
            db.add(mine)
            db.flush()
            department = Department(mine_id=mine.mine_id, name="Mining")
            db.add(department)
            db.flush()
            db.add_all(
                [
                    Worker(employee_code="W-002", name="Zoya", department_id=department.department_id, status="INACTIVE"),
                    Worker(employee_code="W-001", name="Aarav", department_id=department.department_id, status="ACTIVE"),
                ]
            )
            db.commit()

            self.assertEqual(
                fetch_worker_names(db),
                {
                    "count": 2,
                    "workers": [
                        {"name": "Aarav", "employee_code": "W-001"},
                        {"name": "Zoya", "employee_code": "W-002"},
                    ],
                },
            )
        finally:
            db.close()

    def test_recent_worker_tool_uses_rolling_24_hour_window(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        now = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)
        try:
            mine = Mine(name="Test Mine", location="Test", status="ACTIVE")
            db.add(mine)
            db.flush()
            department = Department(mine_id=mine.mine_id, name="Mining")
            db.add(department)
            db.flush()
            db.add_all(
                [
                    Worker(
                        employee_code="W-NEW",
                        name="Recent Worker",
                        department_id=department.department_id,
                        status="ACTIVE",
                        created_at=now - timedelta(hours=23),
                    ),
                    Worker(
                        employee_code="W-OLD",
                        name="Older Worker",
                        department_id=department.department_id,
                        status="ACTIVE",
                        created_at=now - timedelta(hours=25),
                    ),
                    Worker(
                        employee_code="W-FUTURE",
                        name="Future Worker",
                        department_id=department.department_id,
                        status="ACTIVE",
                        created_at=now + timedelta(minutes=1),
                    ),
                ]
            )
            db.commit()

            result = fetch_recent_workers(db, now)
            self.assertEqual(result["window_hours"], 24)
            self.assertEqual(result["count"], 1)
            self.assertEqual(result["workers"][0]["employee_code"], "W-NEW")
            self.assertEqual(result["workers"][0]["added_at"], "2026-09-04T13:00:00Z")
        finally:
            db.close()

    def test_session_start_accepts_toggle_and_push_to_talk(self):
        for mode in ("toggle", "push-to-talk"):
            message = VoiceSessionStart.model_validate(
                {"type": "session.start", "sessionId": "test-session", "mode": mode}
            )
            self.assertEqual(message.mode, mode)

    def test_socket_reports_missing_google_credentials(self):
        settings = get_settings()
        original_key = settings.google_api_key
        settings.google_api_key = ""
        try:
            client = TestClient(app)
            with client.websocket_connect(
                "/api/v1/voice/ws",
                headers={"origin": "http://localhost:5173"},
            ) as websocket:
                websocket.send_json(
                    {
                        "type": "session.start",
                        "sessionId": "test-session",
                        "mode": "toggle",
                    }
                )
                response = websocket.receive_json()
                self.assertEqual(response["type"], "error")
                self.assertEqual(response["code"], "missing_google_api_key")
                self.assertEqual(response["sessionId"], "test-session")
        finally:
            settings.google_api_key = original_key


if __name__ == "__main__":
    unittest.main()
