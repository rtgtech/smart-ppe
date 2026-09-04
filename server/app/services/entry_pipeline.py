"""In-memory face -> PPE entry state machine."""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass, field
from typing import Any

from app.core.config import get_settings
from app.services.ppe_compliance import PPE_ITEM_SPECS


VOTES, WINDOW = 3, 5
IDENTITY_VOTES = 1
ITEMS = {key: value["display_name"] for key, value in PPE_ITEM_SPECS.items()}
SETTINGS = get_settings()


@dataclass
class EntrySession:
    id: str
    phase: str = "IDENTITY"
    lifecycle: str = "ACTIVE"
    verdict: str | None = None
    worker: dict[str, str] | None = None
    identity: list[dict[str, Any]] = field(default_factory=list)
    ppe: list[dict[str, Any]] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    started: float = field(default_factory=time.monotonic)
    touched: float = field(default_factory=time.monotonic)
    identity_timeout: float = SETTINGS.entry_identity_timeout_seconds
    ppe_timeout: float = SETTINGS.entry_evidence_timeout_seconds

    def add_identity(self, faces: list[dict[str, Any]], quality: bool) -> None:
        if len(faces) > 1:
            sample = {"state": "MULTIPLE"}
        elif not faces:
            sample = {"state": "NO_FACE"}
        elif faces[0]["recognized"]:
            sample = {"state": "MATCH", **{key: faces[0].get(key) for key in ("person_id", "name", "similarity")}}
        elif not quality:
            sample = {"state": "LOW_QUALITY"}
        else:
            sample = {"state": "UNKNOWN", "similarity": faces[0].get("similarity")}
        self.identity = (self.identity + [sample])[-WINDOW:]
        self.touched = time.monotonic()
        matches: dict[str, list[dict[str, Any]]] = {}
        for row in self.identity:
            if row["state"] == "MATCH":
                matches.setdefault(row["person_id"], []).append(row)
        person_id = max(matches, key=lambda key: len(matches[key]), default=None)
        if person_id and len(matches[person_id]) >= IDENTITY_VOTES:
            match = matches[person_id][-1]
            self.worker = {"worker_id": person_id, "employee_code": person_id, "name": match["name"], "department": ""}
            self.phase, self.started, self.ppe = "EVIDENCE", time.monotonic(), []
        elif time.monotonic() - self.started >= self.identity_timeout:
            self.finish("HOLD", ["IDENTITY_NOT_CONFIRMED"])

    def add_ppe(self, persons: list[dict[str, Any]], faces: list[dict[str, Any]], quality: bool) -> None:
        recognized = [face for face in faces if face["recognized"]]
        changed = any(face.get("person_id") != self.worker["employee_code"] for face in recognized)
        continuous = len(faces) == len(recognized) == 1 and not changed
        person = persons[0] if len(persons) == 1 else None
        usable = bool(person and quality and continuous)
        self.ppe = (self.ppe + [{
            "changed": changed, "usable": usable,
            "items": {name: {
                "state": person.get(label, "UNKNOWN") if usable else "UNKNOWN",
                "confidence": person.get(f"{label}_confidence", 0) if person else 0,
            } for label, name in ITEMS.items()},
        }])[-WINDOW:]
        self.touched = time.monotonic()
        if sum(row["changed"] for row in self.ppe) >= VOTES:
            self.finish("HOLD", ["IDENTITY_CHANGED_DURING_PPE_CHECK"])
            return
        summary = self.visual()
        missing = [name for name, row in summary.items() if row["state"] == "MISSING"]
        if missing:
            self.finish("DENIED", [f"{name.upper()}_NOT_WORN" for name in missing])
        elif all(row["state"] == "CONFIRMED" for row in summary.values()):
            self.finish("ALLOWED", [])
        elif time.monotonic() - self.started >= self.ppe_timeout:
            self.finish("HOLD", ["PPE_CHECK_INCONCLUSIVE"])

    def visual(self) -> dict[str, dict[str, Any]]:
        output = {}
        for name in ITEMS.values():
            rows = [frame["items"][name] for frame in self.ppe]
            yes, no = [row for row in rows if row["state"] == "YES"], [row for row in rows if row["state"] == "NO"]
            state = "CONFIRMED" if len(yes) >= VOTES else "MISSING" if len(no) >= VOTES else "SCANNING"
            values = [float(row["confidence"]) for row in yes] if state == "CONFIRMED" else [float(row["confidence"]) for row in no]
            output[name] = {"state": state, "positive_frames": len(yes), "negative_frames": len(no), "confidence": round(statistics.median(values) * 100, 1) if values else None}
        return output

    def finish(self, verdict: str, reasons: list[str]) -> None:
        self.lifecycle, self.phase, self.verdict, self.reasons = "FINALIZED", "FINAL", verdict, reasons
        self.touched = time.monotonic()

    def result(self) -> dict[str, Any]:
        matches = [row for row in self.identity if row["state"] == "MATCH" and (not self.worker or row["person_id"] == self.worker["employee_code"])]
        confidence = round(statistics.median(float(row["similarity"]) for row in matches) * 100, 1) if matches else None
        visual = self.visual()
        evidence_confidence = round(min(1, min((max(row["positive_frames"], row["negative_frames"]) / VOTES for row in visual.values()), default=0)) * 100, 1)
        current_identity = "CONFIRMED" if self.worker else (self.identity[-1]["state"] if self.identity else "SEARCHING")
        return {
            "event_id": self.id, "session_id": self.id, "lifecycle": self.lifecycle, "phase": self.phase,
            "verdict": self.verdict, "worker": self.worker, "reasons": self.reasons,
            "evidence": {
                "identity": {"state": current_identity, "confidence": confidence, "supporting_frames": len(matches), "required_frames": IDENTITY_VOTES},
                "framing": {"state": "CONFIRMED" if any(row["usable"] for row in self.ppe) else "SCANNING"},
                "visual": visual, "frames_in_window": len(self.ppe if self.worker else self.identity),
            },
            "identity_confidence": confidence, "ppe_confidence": evidence_confidence, "evidence_confidence": evidence_confidence,
            "interventions": {"barrier": "UNLOCKED" if self.verdict == "ALLOWED" else "LOCKED", "indicator": "GREEN" if self.verdict == "ALLOWED" else "RED" if self.verdict == "DENIED" else "AMBER"},
            "persisted": False, "storage": "TRANSIENT_MEMORY",
        }


class SessionStore:
    def __init__(self) -> None:
        self.sessions: dict[str, EntrySession] = {}

    def create(self, session_id: str) -> EntrySession:
        self.purge()
        return self.sessions.setdefault(session_id, EntrySession(session_id))

    def get(self, session_id: str) -> EntrySession | None:
        self.purge()
        return self.sessions.get(session_id)

    def discard(self, session_id: str) -> bool:
        return self.sessions.pop(session_id, None) is not None

    def purge(self) -> None:
        now = time.monotonic()
        self.sessions = {key: value for key, value in self.sessions.items() if now - value.touched < (120 if value.lifecycle == "FINALIZED" else 600)}


entry_sessions = SessionStore()
