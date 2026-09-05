import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.main import app
from app.models import Base, ComplianceLog, Department, Gate, Mine, PpeDetection, PpeItem, Worker
from app.schemas.voice import VoiceSessionStart
from app.services.voice_agent import VoiceRuntime, _handle_tool_calls, live_config
from app.services.voice_tools import (
    INDIA_TIMEZONE,
    fetch_violations,
    fetch_recent_workers,
    fetch_today_ppe_violations,
    fetch_worker_names,
)


class VoiceAgentTest(unittest.TestCase):
    def test_live_session_only_registers_worker_listing_tools(self):
        config = live_config()
        self.assertEqual(config.speech_config.language_code, "en-IN")
        names = {
            declaration.name
            for tool in config.tools
            for declaration in tool.function_declarations
        }
        self.assertEqual(
            names,
            {
                "list_worker_names",
                "list_recent_workers",
                "get_today_ppe_violations",
                "get_violations",
            },
        )

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

    def test_today_ppe_tool_counts_non_demo_missing_items_in_indian_day(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        now = datetime(2026, 9, 5, 12, 0, tzinfo=INDIA_TIMEZONE)
        try:
            mine = Mine(name="Test Mine", location="Test", status="ACTIVE")
            db.add(mine)
            db.flush()
            department = Department(mine_id=mine.mine_id, name="Mining")
            gate = Gate(mine_id=mine.mine_id, name="Gate 01", location="Entry", status="ACTIVE")
            db.add_all([department, gate])
            db.flush()
            worker = Worker(
                employee_code="W-001",
                name="Aarav",
                department_id=department.department_id,
                status="ACTIVE",
            )
            items = {
                name: PpeItem(name=name, is_mandatory=True)
                for name in ("Gloves", "Helmet", "Shoes", "Vest")
            }
            db.add_all([worker, *items.values()])
            db.flush()

            def add_log(event_id, local_time, missing, data_origin="LIVE"):
                log = ComplianceLog(
                    event_id=event_id,
                    final_verdict="DENIED",
                    worker_id=worker.worker_id,
                    gate_id=gate.gate_id,
                    entry_time=local_time.astimezone(timezone.utc),
                    overall_status="DENIED",
                    compliance_score=0,
                    confidence_score=90,
                    offline_flag=False,
                    sync_status="SYNCED",
                    data_origin=data_origin,
                )
                db.add(log)
                db.flush()
                db.add_all([
                    PpeDetection(
                        log_id=log.log_id,
                        ppe_id=items[name].ppe_id,
                        detected=False,
                        confidence_score=90,
                        detection_source="AI",
                    )
                    for name in missing
                ])

            add_log("today-1", now - timedelta(hours=11), ["Helmet", "Vest"])
            add_log("today-2", now - timedelta(hours=1), ["Gloves", "Helmet", "Shoes"])
            add_log("demo", now - timedelta(hours=2), ["Helmet"], "DEMO")
            add_log("yesterday", now.replace(hour=0) - timedelta(minutes=1), ["Helmet"])
            add_log("future", now + timedelta(minutes=1), ["Vest"])
            db.commit()

            result = fetch_today_ppe_violations(db, now)
            self.assertEqual(result["date"], "2026-09-05")
            self.assertEqual(result["timezone"], "Asia/Kolkata")
            self.assertEqual(result["total_violations"], 5)
            self.assertEqual(result["violation_events"], 2)
            self.assertEqual(
                {row["ppe_item"]: row["violations"] for row in result["by_ppe_item"]},
                {"Helmet": 2, "Boots": 1, "Gloves": 1, "Vest": 1},
            )
            self.assertEqual(result["data_scope"], "NON_DEMO")

            today = fetch_violations(db, "Aarav", "today", now)
            self.assertEqual(today["status"], "OK")
            self.assertEqual(today["worker"]["employee_code"], "W-001")
            self.assertEqual(today["violation_count"], 2)
            self.assertEqual(today["returned_count"], 2)
            self.assertFalse(today["truncated"])
            self.assertEqual(today["violations"][0]["occurred_at"], "2026-09-05T11:00:00+05:30")

            yesterday = fetch_violations(db, "W-001", "yesterday", now)
            self.assertEqual(yesterday["violation_count"], 1)

            empty = fetch_violations(db, date_value="2026-09-03", now=now)
            self.assertEqual(empty["status"], "OK")
            self.assertEqual(empty["violation_count"], 0)
            self.assertEqual(empty["violations"], [])

            missing_worker = fetch_violations(db, "Nobody", "today", now)
            self.assertEqual(missing_worker["status"], "WORKER_NOT_FOUND")
            self.assertEqual(missing_worker["violation_count"], 0)

            invalid_date = fetch_violations(db, date_value="last someday", now=now)
            self.assertEqual(invalid_date["status"], "INVALID_DATE")
            self.assertEqual(invalid_date["violation_count"], 0)

            latest = fetch_violations(db, now=now)
            self.assertEqual(latest["query"]["date"], "latest")
            self.assertEqual(latest["violation_count"], 3)

            db.add(Worker(
                employee_code="W-002",
                name="Aarav",
                department_id=department.department_id,
                status="INACTIVE",
            ))
            db.commit()
            ambiguous = fetch_violations(db, "Aarav", "today", now)
            self.assertEqual(ambiguous["status"], "AMBIGUOUS_WORKER")
            self.assertEqual(len(ambiguous["candidates"]), 2)
            self.assertEqual(ambiguous["violation_count"], 0)
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


class VoiceToolDispatchTest(unittest.IsolatedAsyncioTestCase):
    async def test_today_ppe_result_without_count_reaches_gemini(self):
        result = {
            "date": "2026-09-05",
            "timezone": "Asia/Kolkata",
            "total_violations": 5,
            "violation_events": 2,
            "by_ppe_item": [{"ppe_item": "Helmet", "violations": 5}],
            "data_scope": "NON_DEMO",
        }
        runtime = VoiceRuntime("dispatch-test", AsyncMock(), get_settings())
        live_session = SimpleNamespace(send_tool_response=AsyncMock())
        tool_call = SimpleNamespace(
            function_calls=[
                SimpleNamespace(
                    id="call-1",
                    name="get_today_ppe_violations",
                    args={},
                )
            ]
        )

        with patch(
            "app.services.voice_agent.execute_today_ppe_violations",
            return_value=result,
        ):
            await _handle_tool_calls(runtime, live_session, tool_call)

        live_session.send_tool_response.assert_awaited_once()
        response = live_session.send_tool_response.await_args.kwargs["function_responses"][0]
        self.assertEqual(response.name, "get_today_ppe_violations")
        self.assertEqual(response.response, {"ok": True, "result": result})

    async def test_get_violations_arguments_reach_executor(self):
        result = {"status": "OK", "violation_count": 0, "violations": []}
        runtime = VoiceRuntime("dispatch-test", AsyncMock(), get_settings())
        live_session = SimpleNamespace(send_tool_response=AsyncMock())
        tool_call = SimpleNamespace(
            function_calls=[
                SimpleNamespace(
                    id="call-2",
                    name="get_violations",
                    args={"worker_name": "Aarav", "date": "yesterday"},
                )
            ]
        )

        with patch(
            "app.services.voice_agent.execute_get_violations",
            return_value=result,
        ) as executor:
            await _handle_tool_calls(runtime, live_session, tool_call)

        executor.assert_called_once_with("Aarav", "yesterday")
        response = live_session.send_tool_response.await_args.kwargs["function_responses"][0]
        self.assertEqual(response.response, {"ok": True, "result": result})


if __name__ == "__main__":
    unittest.main()
