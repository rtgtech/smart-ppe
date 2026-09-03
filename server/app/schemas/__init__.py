from app.schemas.alert import AlertCreate, AlertRead, AlertUpdate
from app.schemas.attendance_log import AttendanceLogCreate, AttendanceLogRead, AttendanceLogUpdate
from app.schemas.compliance_log import ComplianceLogCreate, ComplianceLogRead, ComplianceLogUpdate
from app.schemas.department import DepartmentCreate, DepartmentRead, DepartmentUpdate
from app.schemas.device import DeviceCreate, DeviceRead, DeviceUpdate
from app.schemas.gate import GateCreate, GateRead, GateUpdate
from app.schemas.mine import MineCreate, MineRead, MineUpdate
from app.schemas.notification import NotificationCreate, NotificationRead, NotificationUpdate
from app.schemas.ppe_detection import PpeDetectionCreate, PpeDetectionRead, PpeDetectionUpdate
from app.schemas.ppe_item import PpeItemCreate, PpeItemRead, PpeItemUpdate
from app.schemas.report import ReportCreate, ReportRead, ReportUpdate
from app.schemas.safety_score import SafetyScoreCreate, SafetyScoreRead, SafetyScoreUpdate
from app.schemas.worker import WorkerCreate, WorkerRead, WorkerUpdate
from app.schemas.worker_ppe import WorkerPpeCreate, WorkerPpeRead, WorkerPpeUpdate

__all__ = [
    "AlertCreate",
    "AlertRead",
    "AlertUpdate",
    "AttendanceLogCreate",
    "AttendanceLogRead",
    "AttendanceLogUpdate",
    "ComplianceLogCreate",
    "ComplianceLogRead",
    "ComplianceLogUpdate",
    "DepartmentCreate",
    "DepartmentRead",
    "DepartmentUpdate",
    "DeviceCreate",
    "DeviceRead",
    "DeviceUpdate",
    "GateCreate",
    "GateRead",
    "GateUpdate",
    "MineCreate",
    "MineRead",
    "MineUpdate",
    "NotificationCreate",
    "NotificationRead",
    "NotificationUpdate",
    "PpeDetectionCreate",
    "PpeDetectionRead",
    "PpeDetectionUpdate",
    "PpeItemCreate",
    "PpeItemRead",
    "PpeItemUpdate",
    "ReportCreate",
    "ReportRead",
    "ReportUpdate",
    "SafetyScoreCreate",
    "SafetyScoreRead",
    "SafetyScoreUpdate",
    "WorkerCreate",
    "WorkerRead",
    "WorkerUpdate",
    "WorkerPpeCreate",
    "WorkerPpeRead",
    "WorkerPpeUpdate",
]
