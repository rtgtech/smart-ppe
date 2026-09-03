from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


MineStatus = Literal["ACTIVE", "INACTIVE"]
WorkerStatus = Literal["ACTIVE", "INACTIVE"]
GateStatus = Literal["ACTIVE", "MAINTENANCE", "OFFLINE"]
DeviceType = Literal["AI_CAMERA", "RFID_READER", "NFC_READER", "GAS_SENSOR", "GATE_CONTROLLER"]
DeviceStatus = Literal["ONLINE", "OFFLINE", "MAINTENANCE"]
WorkerPpeStatus = Literal["ACTIVE", "EXPIRED"]
ComplianceStatus = Literal["COMPLIANT", "NON_COMPLIANT", "DENIED"]
SyncStatus = Literal["PENDING", "SYNCED", "FAILED"]
AttendanceStatus = Literal["PRESENT", "INSIDE", "OUTSIDE", "ABSENT"]
DetectionSource = Literal["AI", "RFID", "SENSOR"]
AlertSeverity = Literal["INFO", "WARNING", "CRITICAL"]
AlertStatus = Literal["ACTIVE", "RESOLVED", "CLOSED"]
NotificationChannel = Literal["SMS", "EMAIL", "PUSH", "APP"]
NotificationStatus = Literal["SENT", "FAILED", "PENDING"]
RiskLevel = Literal["LOW", "MEDIUM", "HIGH"]
ReportType = Literal["DAILY", "WEEKLY", "MONTHLY", "WORKER_WISE", "GATE_WISE", "PPE_WISE"]


Score = Annotated[float, Field(ge=0, le=100)]
Latitude = Annotated[float, Field(ge=-90, le=90)]
Longitude = Annotated[float, Field(ge=-180, le=180)]


__all__ = [
    "AlertSeverity",
    "AlertStatus",
    "AttendanceStatus",
    "ComplianceStatus",
    "DetectionSource",
    "DeviceStatus",
    "DeviceType",
    "GateStatus",
    "Latitude",
    "Longitude",
    "MineStatus",
    "NotificationChannel",
    "NotificationStatus",
    "OrmModel",
    "ReportType",
    "RiskLevel",
    "Score",
    "SyncStatus",
    "WorkerPpeStatus",
    "WorkerStatus",
    "date",
    "datetime",
]
