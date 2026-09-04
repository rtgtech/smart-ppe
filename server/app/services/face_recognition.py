"""Face enrollment and nearest-template recognition."""

from __future__ import annotations

import json
import os
import re
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.services.edgeface import EdgeFaceEmbedder, align_face
from app.services.scrfd import DetectedFace, SCRFDDetector


EMBEDDING_MODEL_VERSION = "edgeface-s-gamma-05-v1"
LEGACY_EMBEDDING_MODEL_VERSION = "opencv-sface-2021dec-v1"
_ID = re.compile(r"^[A-Z0-9_-]{1,64}$")


class FaceServiceError(ValueError):
    pass


def normalize_embedding(value: np.ndarray | list[float]) -> np.ndarray:
    vector = np.asarray(value, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(vector))
    if not vector.size or not np.isfinite(vector).all() or norm <= 1e-8:
        raise FaceServiceError("Invalid face embedding")
    return vector / norm


def validate_person_id(value: str) -> str:
    value = value.strip().upper()
    if not _ID.fullmatch(value):
        raise FaceServiceError("Person ID must use 1-64 letters, numbers, underscores, or hyphens")
    return value


def validate_name(value: str) -> str:
    value = " ".join(value.split())
    if not value or len(value) > 100:
        raise FaceServiceError("Name must contain 1-100 characters")
    return value


class FaceRegistry:
    """JSON template store. Entry results are never written here."""

    def __init__(self, path: Path) -> None:
        self.path, self._lock, self._profiles = path, threading.RLock(), {}
        if path.exists():
            try:
                self._profiles = json.loads(path.read_text(encoding="utf-8")).get("profiles", {})
            except (OSError, json.JSONDecodeError) as exc:
                raise FaceServiceError(f"Invalid face registry: {exc}") from exc

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps({"schema_version": 1, "profiles": self._profiles}, indent=2), encoding="utf-8")
        os.replace(temporary, self.path)

    @staticmethod
    def _public(profile: dict[str, Any]) -> dict[str, Any]:
        return {key: profile.get(key) for key in ("person_id", "name", "embedding_model", "enrolled_at", "updated_at")} | {
            "requires_reenrollment": profile.get("embedding_model") != EMBEDDING_MODEL_VERSION
        }

    def count(self, model: str | None = None) -> int:
        with self._lock:
            return sum(not model or row.get("embedding_model") == model for row in self._profiles.values())

    def list_profiles(self) -> list[dict[str, Any]]:
        with self._lock:
            return sorted((self._public(row) for row in self._profiles.values()), key=lambda row: (str(row["name"]).lower(), str(row["person_id"])))

    def embeddings(self, model: str = EMBEDDING_MODEL_VERSION) -> list[tuple[str, str, np.ndarray]]:
        with self._lock:
            return [
                (person_id, row.get("name", person_id), normalize_embedding(row["embedding"]))
                for person_id, row in self._profiles.items()
                if row.get("embedding_model") == model and row.get("embedding")
            ]

    def create(self, person_id: str, name: str, embedding: np.ndarray) -> dict[str, Any]:
        person_id, name = validate_person_id(person_id), validate_name(name)
        with self._lock:
            if person_id in self._profiles:
                raise FileExistsError(f"Profile {person_id} already exists")
            now = datetime.now(timezone.utc).isoformat()
            self._profiles[person_id] = {"person_id": person_id, "name": name, "embedding": normalize_embedding(embedding).tolist(), "embedding_model": EMBEDDING_MODEL_VERSION, "enrolled_at": now, "updated_at": now}
            try:
                self._save()
            except Exception:
                self._profiles.pop(person_id, None)
                raise
            return self._public(self._profiles[person_id])

    def replace_embedding(self, person_id: str, embedding: np.ndarray) -> dict[str, Any]:
        person_id = validate_person_id(person_id)
        with self._lock:
            if person_id not in self._profiles:
                raise KeyError(person_id)
            self._profiles[person_id].update(embedding=normalize_embedding(embedding).tolist(), embedding_model=EMBEDDING_MODEL_VERSION, updated_at=datetime.now(timezone.utc).isoformat())
            self._save()
            return self._public(self._profiles[person_id])

    def delete(self, person_id: str) -> bool:
        with self._lock:
            removed = self._profiles.pop(validate_person_id(person_id), None)
            if removed:
                self._save()
            return removed is not None

    def profile_snapshot(self, person_id: str) -> dict[str, Any] | None:
        with self._lock:
            return deepcopy(self._profiles.get(validate_person_id(person_id)))

    def restore_snapshot(self, profile: dict[str, Any]) -> None:
        with self._lock:
            self._profiles[validate_person_id(profile["person_id"])] = deepcopy(profile)
            self._save()


class FaceEngine:
    def __init__(self, detector_path: Path, recognizer_path: Path, similarity_threshold: float = .4, detector_score_threshold: float = .5, detector_nms_threshold: float = .4, detector_input_size: int = 640, device: str | None = None) -> None:
        self.detector = SCRFDDetector(detector_path, detector_score_threshold, detector_nms_threshold, (detector_input_size, detector_input_size), device)
        self.recognizer = EdgeFaceEmbedder(recognizer_path, device)
        self.similarity_threshold = similarity_threshold
        self.embedding_model = EMBEDDING_MODEL_VERSION

    def detect(self, image: np.ndarray) -> list[DetectedFace]:
        return self.detector.detect(image)

    def embedding_for_face(self, image: np.ndarray, face: DetectedFace) -> np.ndarray:
        if min(face.bbox[2] - face.bbox[0], face.bbox[3] - face.bbox[1]) < 64:
            raise FaceServiceError("Move closer to the camera")
        return normalize_embedding(self.recognizer.embed(align_face(image, face.landmarks)))

    def enrollment_embedding(self, images: list[np.ndarray]) -> np.ndarray:
        if len(images) != 5:
            raise FaceServiceError("Exactly five captures are required")
        vectors = []
        for index, image in enumerate(images, 1):
            faces = [face for face in self.detect(image) if min(face.bbox[2] - face.bbox[0], face.bbox[3] - face.bbox[1]) >= 64]
            if not faces:
                raise FaceServiceError(f"Capture {index}: move closer so your face is clearly visible")
            primary = max(faces, key=lambda face: (face.bbox[2] - face.bbox[0]) * (face.bbox[3] - face.bbox[1]))
            primary_area = (primary.bbox[2] - primary.bbox[0]) * (primary.bbox[3] - primary.bbox[1])
            foreground = [face for face in faces if (face.bbox[2] - face.bbox[0]) * (face.bbox[3] - face.bbox[1]) >= primary_area * .35]
            if len(foreground) > 1:
                raise FaceServiceError(f"Capture {index}: keep only one nearby face in frame")
            vectors.append(self.embedding_for_face(image, primary))
        return normalize_embedding(np.mean(vectors, axis=0))

    def recognize(self, image: np.ndarray, candidates: list[tuple[str, str, np.ndarray]]) -> list[dict[str, Any]]:
        output = []
        for face in self.detect(image):
            try:
                embedding = self.embedding_for_face(image, face)
            except FaceServiceError:
                output.append({"bbox": [int(round(value)) for value in face.bbox], "recognized": False, "ignored": True, "person_id": None, "name": "Move closer", "similarity": None})
                continue
            matches = [(float(np.dot(embedding, vector)), person_id, name) for person_id, name, vector in candidates if vector.shape == embedding.shape]
            match = max(matches, default=None)
            known = bool(match and match[0] >= self.similarity_threshold)
            output.append({
                "bbox": [int(round(value)) for value in face.bbox], "recognized": known, "ignored": False,
                "person_id": match[1] if known else None, "name": match[2] if known else "Unknown",
                "similarity": round(match[0], 4) if match else None,
            })
        return output


def annotate_faces(image: np.ndarray, faces: list[dict[str, Any]]) -> np.ndarray:
    for face in faces:
        x1, y1, x2, y2 = face["bbox"]
        color = (71, 255, 201) if face["recognized"] else (68, 190, 255)
        label = face["name"] if face["similarity"] is None else f'{face["name"]} {face["similarity"]:.2f}'
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
        cv2.putText(image, label, (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, .55, color, 2)
    return image
