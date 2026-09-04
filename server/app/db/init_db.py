import uuid
from datetime import date, datetime

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.models import Base, Department, Device, Gate, Mine, PpeDetection, PpeItem, SafetyScore, SeedState, Worker, WorkerPpe
from app.db.session import engine
from app.db.seed_ppe_data import PPE_CATALOG, seed_ppe_demo_data


DEFAULT_PPE = [(name, details["description"]) for name, details in PPE_CATALOG.items()]

DEFAULT_WORKERS = [
    ("WK10234", "Ramesh Kumar", "Mining", 92, "HIGH", 7),
    ("WK10211", "Arun Kumar", "Operations", 99, "LOW", 0),
    ("WK10209", "Sanjay Singh", "Electrical", 88, "MEDIUM", 3),
    ("WK10198", "Vikram Yadav", "Maintenance", 81, "HIGH", 9),
    ("WK10187", "Rahul Sharma", "Mining", 97, "LOW", 1),
]

WORKER_SEED_KEY = "initial-demo-workers-v1"
PPE_SEED_KEY = "ppe-demo-v2"


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)


def migrate_entry_schema() -> None:
    """Upgrade legacy SQLite databases without discarding operational records."""
    if not engine.url.drivername.startswith("sqlite"):
        Base.metadata.create_all(bind=engine)
        return

    inspector = inspect(engine)
    if inspector.has_table("worker_ppe"):
        id_column = next(column for column in inspector.get_columns("worker_ppe") if column["name"] == "worker_ppe_id")
        if "INT" in str(id_column["type"]).upper():
            with engine.connect() as connection:
                connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
                connection.exec_driver_sql("ALTER TABLE worker_ppe RENAME TO worker_ppe_legacy")
                for index in ("ix_worker_ppe_worker_id", "ix_worker_ppe_ppe_id"):
                    connection.exec_driver_sql(f"DROP INDEX IF EXISTS {index}")
                WorkerPpe.__table__.create(bind=connection)
                rows = connection.exec_driver_sql(
                    "SELECT worker_ppe_id, worker_id, ppe_id, rfid_tag, serial_number, issued_at, expiry_date, status FROM worker_ppe_legacy"
                ).mappings().all()
                for row in rows:
                    issued_at = row["issued_at"]
                    expiry_date = row["expiry_date"]
                    if isinstance(issued_at, str):
                        issued_at = datetime.fromisoformat(issued_at)
                    if isinstance(expiry_date, str):
                        expiry_date = date.fromisoformat(expiry_date)
                    connection.execute(WorkerPpe.__table__.insert().values(
                        worker_ppe_id=str(uuid.uuid4()), legacy_worker_ppe_id=row["worker_ppe_id"],
                        worker_id=row["worker_id"], ppe_id=row["ppe_id"], rfid_tag=row["rfid_tag"],
                        serial_number=row["serial_number"], issued_at=issued_at,
                        expiry_date=expiry_date, status=row["status"],
                    ))
                connection.exec_driver_sql("DROP TABLE worker_ppe_legacy")
                connection.commit()
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")

    inspector = inspect(engine)
    if inspector.has_table("ppe_detections") and "evidence_state" not in {c["name"] for c in inspector.get_columns("ppe_detections")}:
        with engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            connection.exec_driver_sql("ALTER TABLE ppe_detections RENAME TO ppe_detections_legacy")
            for index in ("ix_ppe_detections_log_id", "ix_ppe_detections_ppe_id"):
                connection.exec_driver_sql(f"DROP INDEX IF EXISTS {index}")
            PpeDetection.__table__.create(bind=connection)
            connection.exec_driver_sql(
                "INSERT INTO ppe_detections (detection_id, log_id, ppe_id, detected, confidence_score, bounding_box, detection_source, created_at) "
                "SELECT detection_id, log_id, ppe_id, detected, confidence_score, bounding_box, detection_source, created_at FROM ppe_detections_legacy"
            )
            connection.exec_driver_sql("DROP TABLE ppe_detections_legacy")
            connection.commit()
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")

    additions = {
        "compliance_logs": [
            ("event_id", "VARCHAR(36)"), ("final_verdict", "VARCHAR(16)"),
        ],
        "attendance_logs": [("event_id", "VARCHAR(36)")],
        "alerts": [("event_id", "VARCHAR(36)"), ("gate_id", "INTEGER REFERENCES gates(gate_id) ON DELETE SET NULL")],
    }
    with engine.begin() as connection:
        for table, columns in additions.items():
            if not inspect(engine).has_table(table):
                continue
            existing = {c["name"] for c in inspect(engine).get_columns(table)}
            for name, sql_type in columns:
                if name not in existing:
                    connection.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {sql_type}")
        index_statements = {
            "compliance_logs": (
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_compliance_logs_event_id ON compliance_logs(event_id)",
                "CREATE INDEX IF NOT EXISTS ix_compliance_logs_final_verdict ON compliance_logs(final_verdict)",
            ),
            "attendance_logs": ("CREATE UNIQUE INDEX IF NOT EXISTS ux_attendance_logs_event_id ON attendance_logs(event_id)",),
            "alerts": (
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_alerts_event_id ON alerts(event_id)",
                "CREATE INDEX IF NOT EXISTS ix_alerts_gate_id ON alerts(gate_id)",
            ),
        }
        for table, statements in index_statements.items():
            if inspect(engine).has_table(table):
                for statement in statements:
                    connection.exec_driver_sql(statement)


def migrate_worker_schema() -> None:
    """Remove the retired worker email field from existing databases."""
    inspector = inspect(engine)
    if not inspector.has_table("workers"):
        return

    worker_columns = {column["name"] for column in inspector.get_columns("workers")}
    if "email" in worker_columns:
        with engine.begin() as connection:
            connection.exec_driver_sql("ALTER TABLE workers DROP COLUMN email")


def seed_initial_data(db: Session) -> None:
    mine = db.query(Mine).filter(Mine.name == "Central Coal Mine").one_or_none()
    if mine is None:
        mine = Mine(name="Central Coal Mine", location="Jharkhand", status="ACTIVE")
        db.add(mine)
        db.flush()

    departments: dict[str, Department] = {}
    for name in {row[2] for row in DEFAULT_WORKERS}:
        department = (
            db.query(Department)
            .filter(Department.mine_id == mine.mine_id, Department.name == name)
            .one_or_none()
        )
        if department is None:
            department = Department(mine_id=mine.mine_id, name=name)
            db.add(department)
            db.flush()
        departments[name] = department

    legacy_departments = db.query(Department).filter(Department.name == "Underground Mining").all()
    for legacy_department in legacy_departments:
        mining_department = (
            db.query(Department)
            .filter(
                Department.mine_id == legacy_department.mine_id,
                Department.name == "Mining",
            )
            .one_or_none()
        )
        if mining_department is None:
            mining_department = Department(mine_id=legacy_department.mine_id, name="Mining")
            db.add(mining_department)
            db.flush()
        db.query(Worker).filter(Worker.department_id == legacy_department.department_id).update(
            {Worker.department_id: mining_department.department_id},
            synchronize_session=False,
        )
        db.delete(legacy_department)
    db.flush()

    for ppe_name, description in DEFAULT_PPE:
        exists = db.query(PpeItem).filter(PpeItem.name == ppe_name).one_or_none()
        if exists is None:
            db.add(PpeItem(name=ppe_name, description=description, is_mandatory=True))

    gate = db.query(Gate).filter(Gate.mine_id == mine.mine_id, Gate.name == "Gate 01").one_or_none()
    if gate is None:
        gate = Gate(mine_id=mine.mine_id, name="Gate 01", location="Main Shaft Entry", latitude=23.7957, longitude=86.4304, status="ACTIVE")
        db.add(gate)
    else:
        gate.latitude = gate.latitude if gate.latitude is not None else 23.7957
        gate.longitude = gate.longitude if gate.longitude is not None else 86.4304

    db.flush()
    if db.query(Device).filter(Device.serial_number == "AI-CAM-G01").one_or_none() is None:
        db.add(Device(gate_id=gate.gate_id, device_type="AI_CAMERA", serial_number="AI-CAM-G01", status="ONLINE"))

    worker_seed = db.get(SeedState, WORKER_SEED_KEY)
    should_seed_workers = worker_seed is None and db.query(Worker).count() == 0
    if worker_seed is None:
        db.add(SeedState(key=WORKER_SEED_KEY))

    if should_seed_workers:
        for code, name, dept_name, score, risk, violations in DEFAULT_WORKERS:
            worker = Worker(
                employee_code=code,
                name=name,
                department_id=departments[dept_name].department_id,
                status="ACTIVE",
            )
            db.add(worker)
            db.flush()
            db.add(SafetyScore(worker_id=worker.worker_id, score=score, risk_level=risk, violation_count=violations, compliance_rate=score))

    db.commit()

    if db.get(SeedState, PPE_SEED_KEY) is None:
        seed_ppe_demo_data(db)
        db.add(SeedState(key=PPE_SEED_KEY))
        db.commit()


def init_db() -> None:
    migrate_entry_schema()
    create_tables()
    migrate_worker_schema()
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        seed_initial_data(db)
    finally:
        db.close()
