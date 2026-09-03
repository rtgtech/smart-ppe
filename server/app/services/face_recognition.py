"""Local face enrollment and recognition using OpenCV YuNet and SFace."""

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


PROFILE_ID_PATTERN = re.compile(r"^[A-Z0-9_-]{1,64}$")
REGISTRY_SCHEMA_VERSION = 1
EMBEDDING_MODEL_VERSION = "opencv-sface-2021dec-v1"


class FaceServiceError(ValueError):
    """Raised when a face image, profile, or model cannot be used safely."""


def normalize_embedding(vector: np.ndarray | list[float]) -> np.ndarray:
    array = np.asarray(vector, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(array))
    if array.size == 0 or not np.isfinite(array).all() or norm <= 1e-8:
        raise FaceServiceError("The face model produced an invalid embedding.")
    return array / norm


def average_embeddings(vectors: list[np.ndarray]) -> np.ndarray:
    if not vectors:
        raise FaceServiceError("At least one face embedding is required.")
    normalized = [normalize_embedding(vector) for vector in vectors]
    dimensions = {vector.shape for vector in normalized}
    if len(dimensions) != 1:
        raise FaceServiceError("Face embeddings have inconsistent dimensions.")
    return normalize_embedding(np.mean(np.stack(normalized), axis=0))


def validate_person_id(person_id: str) -> str:
    normalized = person_id.strip().upper()
    if not PROFILE_ID_PATTERN.fullmatch(normalized):
        raise FaceServiceError(
            "Person ID must contain 1-64 letters, numbers, underscores, or hyphens."
        )
    return normalized


def validate_name(name: str) -> str:
    normalized = " ".join(name.strip().split())
    if not normalized:
        raise FaceServiceError("Name is required.")
    if len(normalized) > 100:
        raise FaceServiceError("Name must be 100 characters or fewer.")
    return normalized


class FaceRegistry:
    """Thread-safe, atomically persisted local face-template registry."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.RLock()
        self._profiles: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        with self._lock:
            if not self.path.exists():
                self._profiles = {}
                return
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise FaceServiceError(f"Could not read face registry: {exc}") from exc
            if not isinstance(payload, dict) or not isinstance(payload.get("profiles"), dict):
                raise FaceServiceError("Face registry has an invalid structure.")
            self._profiles = payload["profiles"]

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": REGISTRY_SCHEMA_VERSION,
            "profiles": self._profiles,
        }
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            os.replace(temporary, self.path)
        except OSError as exc:
            raise FaceServiceError(f"Could not save face registry: {exc}") from exc

    def list_profiles(self) -> list[dict[str, Any]]:
        with self._lock:
            profiles = [self._public_profile(profile) for profile in self._profiles.values()]
        return sorted(profiles, key=lambda profile: (profile["name"].lower(), profile["person_id"]))

    def count(self) -> int:
        with self._lock:
            return len(self._profiles)

    def embeddings(self) -> list[tuple[str, str, np.ndarray]]:
        candidates: list[tuple[str, str, np.ndarray]] = []
        with self._lock:
            for person_id, profile in self._profiles.items():
                try:
                    embedding = normalize_embedding(profile.get("embedding", []))
                except FaceServiceError:
                    continue
                candidates.append((person_id, str(profile.get("name", person_id)), embedding))
        return candidates

    def create(self, person_id: str, name: str, embedding: np.ndarray) -> dict[str, Any]:
        person_id = validate_person_id(person_id)
        name = validate_name(name)
        vector = normalize_embedding(embedding)
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            if person_id in self._profiles:
                raise FileExistsError(f"A profile with ID {person_id} already exists.")
            profile = {
                "person_id": person_id,
                "name": name,
                "embedding": vector.astype(float).tolist(),
                "embedding_model": EMBEDDING_MODEL_VERSION,
                "enrolled_at": now,
                "updated_at": now,
            }
            self._profiles[person_id] = profile
            try:
                self._save()
            except FaceServiceError:
                self._profiles.pop(person_id, None)
                raise
            return self._public_profile(profile)

    def replace_embedding(self, person_id: str, embedding: np.ndarray) -> dict[str, Any]:
        person_id = validate_person_id(person_id)
        vector = normalize_embedding(embedding)
        with self._lock:
            profile = self._profiles.get(person_id)
            if profile is None:
                raise KeyError(person_id)
            previous = deepcopy(profile)
            profile["embedding"] = vector.astype(float).tolist()
            profile["embedding_model"] = EMBEDDING_MODEL_VERSION
            profile["updated_at"] = datetime.now(timezone.utc).isoformat()
            try:
                self._save()
            except FaceServiceError:
                self._profiles[person_id] = previous
                raise
            return self._public_profile(profile)

    def delete(self, person_id: str) -> bool:
        person_id = validate_person_id(person_id)
        with self._lock:
            removed = self._profiles.pop(person_id, None)
            if removed is None:
                return False
            try:
                self._save()
            except FaceServiceError:
                self._profiles[person_id] = removed
                raise
            return True

    def profile_snapshot(self, person_id: str) -> dict[str, Any] | None:
        """Return a private copy used only to roll back coordinated deletion."""
        person_id = validate_person_id(person_id)
        with self._lock:
            profile = self._profiles.get(person_id)
            return deepcopy(profile) if profile is not None else None

    def restore_snapshot(self, profile: dict[str, Any]) -> None:
        """Restore a profile after a related database transaction fails."""
        person_id = validate_person_id(str(profile.get("person_id", "")))
        with self._lock:
            previous = self._profiles.get(person_id)
            self._profiles[person_id] = deepcopy(profile)
            try:
                self._save()
            except FaceServiceError:
                if previous is None:
                    self._profiles.pop(person_id, None)
                else:
                    self._profiles[person_id] = previous
                raise

    @staticmethod
    def _public_profile(profile: dict[str, Any]) -> dict[str, Any]:
        return {
            "person_id": profile["person_id"],
            "name": profile["name"],
            "embedding_model": profile.get("embedding_model", EMBEDDING_MODEL_VERSION),
            "enrolled_at": profile.get("enrolled_at"),
            "updated_at": profile.get("updated_at"),
        }


class FaceEngine:
    """YuNet detection, SFace alignment/embedding, and nearest-profile matching."""

    def __init__(
        self,
        detector_path: Path,
        recognizer_path: Path,
        similarity_threshold: float = 0.363,
        detector_score_threshold: float = 0.9,
    ) -> None:
        missing = [str(path) for path in (detector_path, recognizer_path) if not path.is_file()]
        if missing:
            raise FileNotFoundError(
                "Face model file(s) missing: " + ", ".join(missing)
                + ". Download the YuNet and SFace ONNX files described in stream_test/README.md."
            )
        if not 0.0 < similarity_threshold < 1.0:
            raise FaceServiceError("Face similarity threshold must be between 0 and 1.")

        self.detector_path = detector_path
        self.recognizer_path = recognizer_path
        self.similarity_threshold = similarity_threshold
        self.detector = cv2.FaceDetectorYN.create(
            str(detector_path), "", (320, 320), detector_score_threshold, 0.3, 5000
        )
        self.recognizer = cv2.FaceRecognizerSF.create(str(recognizer_path), "")

    def detect(self, image: np.ndarray) -> list[np.ndarray]:
        if image is None or image.size == 0:
            raise FaceServiceError("A valid image is required.")
        height, width = image.shape[:2]
        self.detector.setInputSize((width, height))
        _, detected = self.detector.detect(image)
        if detected is None:
            return []
        return [face.astype(np.float32) for face in detected]

    def embedding_for_face(self, image: np.ndarray, face: np.ndarray) -> np.ndarray:
        width, height = float(face[2]), float(face[3])
        if min(width, height) < 64:
            raise FaceServiceError("Move closer to the camera so the face is at least 64 pixels wide.")
        aligned = self.recognizer.alignCrop(image, face)
        feature = self.recognizer.feature(aligned)
        return normalize_embedding(feature)

    def enrollment_embedding(self, images: list[np.ndarray]) -> np.ndarray:
        if len(images) != 5:
            raise FaceServiceError("Registration requires exactly five face images.")
        embeddings: list[np.ndarray] = []
        for index, image in enumerate(images, start=1):
            faces = self.detect(image)
            if len(faces) != 1:
                if not faces:
                    detail = "no face was detected"
                else:
                    detail = f"{len(faces)} faces were detected"
                raise FaceServiceError(f"Capture {index} is invalid: {detail}; exactly one is required.")
            embeddings.append(self.embedding_for_face(image, faces[0]))
        return average_embeddings(embeddings)

    def recognize(
        self,
        image: np.ndarray,
        candidates: list[tuple[str, str, np.ndarray]],
    ) -> list[dict[str, Any]]:
        recognized: list[dict[str, Any]] = []
        image_height, image_width = image.shape[:2]
        for face in self.detect(image):
            x, y, width, height = (int(round(value)) for value in face[:4])
            x1 = max(0, min(image_width - 1, x))
            y1 = max(0, min(image_height - 1, y))
            x2 = max(x1, min(image_width - 1, x + width))
            y2 = max(y1, min(image_height - 1, y + height))
            try:
                embedding = self.embedding_for_face(image, face)
            except FaceServiceError:
                recognized.append(
                    {
                        "bbox": [x1, y1, x2, y2],
                        "recognized": False,
                        "person_id": None,
                        "name": "Unknown",
                        "similarity": None,
                    }
                )
                continue
            match: tuple[float, str, str] | None = None
            for person_id, name, candidate in candidates:
                if candidate.shape != embedding.shape:
                    continue
                similarity = float(np.dot(embedding, candidate))
                if match is None or similarity > match[0]:
                    match = (similarity, person_id, name)

            is_recognized = match is not None and match[0] >= self.similarity_threshold
            recognized.append(
                {
                    "bbox": [x1, y1, x2, y2],
                    "recognized": is_recognized,
                    "person_id": match[1] if is_recognized and match else None,
                    "name": match[2] if is_recognized and match else "Unknown",
                    "similarity": round(match[0], 4) if match else None,
                }
            )
        return recognized


def annotate_faces(image: np.ndarray, faces: list[dict[str, Any]]) -> np.ndarray:
    """Draw readable face boxes and identity labels on an existing annotated frame."""
    for face in faces:
        x1, y1, x2, y2 = face["bbox"]
        color = (71, 255, 201) if face["recognized"] else (68, 190, 255)
        label = face["name"]
        if face["recognized"] and face["similarity"] is not None:
            label = f"{label} {face['similarity']:.2f}"
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 2, cv2.LINE_AA)
        (text_width, text_height), baseline = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1
        )
        label_top = max(0, y1 - text_height - baseline - 8)
        cv2.rectangle(
            image,
            (x1, label_top),
            (x1 + text_width + 10, label_top + text_height + baseline + 8),
            color,
            -1,
        )
        cv2.putText(
            image,
            label,
            (x1 + 5, label_top + text_height + 3),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (8, 11, 16),
            1,
            cv2.LINE_AA,
        )
    return image
