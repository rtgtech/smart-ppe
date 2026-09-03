from sqlalchemy.orm import Session

from app.models import Base, Department, Gate, Mine, PpeItem, SafetyScore, Worker
from app.db.session import engine
from app.db.seed_ppe_data import PPE_CATALOG, seed_ppe_demo_data


DEFAULT_PPE = [(name, details["description"]) for name, details in PPE_CATALOG.items()]

DEFAULT_WORKERS = [
    ("WK10234", "Ramesh Kumar", "Underground Mining", "A", "RFID-8F31A9", 92, "HIGH", 7),
    ("WK10211", "Arun Kumar", "Operations", "A", "RFID-2C10B4", 99, "LOW", 0),
    ("WK10209", "Sanjay Singh", "Electrical", "B", "RFID-77AE02", 88, "MEDIUM", 3),
    ("WK10198", "Vikram Yadav", "Maintenance", "A", "RFID-441FDD", 81, "HIGH", 9),
    ("WK10187", "Rahul Sharma", "Mining", "B", "RFID-9B0021", 97, "LOW", 1),
]


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)


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

    for ppe_name, description in DEFAULT_PPE:
        exists = db.query(PpeItem).filter(PpeItem.name == ppe_name).one_or_none()
        if exists is None:
            db.add(PpeItem(name=ppe_name, description=description, is_mandatory=True))

    gate = db.query(Gate).filter(Gate.mine_id == mine.mine_id, Gate.name == "Gate 01").one_or_none()
    if gate is None:
        db.add(Gate(mine_id=mine.mine_id, name="Gate 01", location="Main Shaft Entry", status="ACTIVE"))

    db.flush()

    for code, name, dept_name, shift, rfid_uid, score, risk, violations in DEFAULT_WORKERS:
        exists = db.query(Worker).filter(Worker.employee_code == code).one_or_none()
        worker = exists
        if worker is None:
            worker = Worker(
                employee_code=code,
                name=name,
                department_id=departments[dept_name].department_id,
                designation=f"Shift {shift}",
                rfid_uid=rfid_uid,
                status="ACTIVE",
            )
            db.add(worker)
            db.flush()
            db.add(SafetyScore(worker_id=worker.worker_id, score=score, risk_level=risk, violation_count=violations, compliance_rate=score))

    db.commit()
    seed_ppe_demo_data(db)


def init_db() -> None:
    create_tables()
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        seed_initial_data(db)
    finally:
        db.close()
