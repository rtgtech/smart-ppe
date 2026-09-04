"""Minimal SCRFD ONNX adapter used by the face pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort


@dataclass(frozen=True)
class DetectedFace:
    bbox: np.ndarray
    landmarks: np.ndarray
    score: float


def _distance_to_bbox(centers: np.ndarray, distance: np.ndarray) -> np.ndarray:
    return np.column_stack(
        (centers[:, 0] - distance[:, 0], centers[:, 1] - distance[:, 1],
         centers[:, 0] + distance[:, 2], centers[:, 1] + distance[:, 3])
    )


def _distance_to_landmarks(centers: np.ndarray, distance: np.ndarray) -> np.ndarray:
    decoded = np.empty_like(distance, dtype=np.float32)
    for point in range(5):
        decoded[:, point * 2] = centers[:, 0] + distance[:, point * 2]
        decoded[:, point * 2 + 1] = centers[:, 1] + distance[:, point * 2 + 1]
    return decoded


class SCRFDDetector:
    def __init__(
        self,
        model_path: Path,
        score_threshold: float = 0.5,
        nms_threshold: float = 0.4,
        input_size: tuple[int, int] = (640, 640),
        device: str | None = None,
    ) -> None:
        if not model_path.is_file():
            raise FileNotFoundError(f"SCRFD model not found: {model_path}")
        available = set(ort.get_available_providers())
        wants_cuda = bool(device and str(device).lower() not in {"cpu", "-1"})
        providers = (["CUDAExecutionProvider"] if wants_cuda and "CUDAExecutionProvider" in available else []) + ["CPUExecutionProvider"]
        self.session = ort.InferenceSession(str(model_path), providers=providers)
        self.provider = self.session.get_providers()[0]
        self.input_name = self.session.get_inputs()[0].name
        self.output_names = [output.name for output in self.session.get_outputs()]
        self.score_threshold = score_threshold
        self.nms_threshold = nms_threshold
        self.input_size = input_size
        if len(self.output_names) == 9:
            self.strides, self.anchor_count = (8, 16, 32), 2
        elif len(self.output_names) == 15:
            self.strides, self.anchor_count = (8, 16, 32, 64, 128), 1
        else:
            raise RuntimeError("SCRFD must expose scores, boxes, and five landmarks per feature map")
        self.feature_count = len(self.strides)
        self._centers: dict[tuple[int, int, int], np.ndarray] = {}

    def _anchor_centers(self, height: int, width: int, stride: int) -> np.ndarray:
        key = (height, width, stride)
        if key not in self._centers:
            grid = np.stack(np.mgrid[:height, :width][::-1], axis=-1).astype(np.float32)
            centers = (grid * stride).reshape(-1, 2)
            self._centers[key] = np.repeat(centers, self.anchor_count, axis=0)
        return self._centers[key]

    def detect(self, image: np.ndarray) -> list[DetectedFace]:
        if image is None or image.size == 0:
            raise ValueError("A non-empty image is required")
        source_height, source_width = image.shape[:2]
        input_width, input_height = self.input_size
        scale = min(input_width / source_width, input_height / source_height)
        resized_width, resized_height = int(round(source_width * scale)), int(round(source_height * scale))
        canvas = np.zeros((input_height, input_width, 3), dtype=np.uint8)
        canvas[:resized_height, :resized_width] = cv2.resize(image, (resized_width, resized_height))
        blob = cv2.dnn.blobFromImage(canvas, 1 / 128.0, self.input_size, (127.5,) * 3, swapRB=True)
        outputs = self.session.run(self.output_names, {self.input_name: blob})

        all_scores, all_boxes, all_landmarks = [], [], []
        for index, stride in enumerate(self.strides):
            scores = np.asarray(outputs[index]).reshape(-1)
            boxes = np.asarray(outputs[index + self.feature_count]).reshape(-1, 4) * stride
            landmarks = np.asarray(outputs[index + self.feature_count * 2]).reshape(-1, 10) * stride
            centers = self._anchor_centers(input_height // stride, input_width // stride, stride)
            selected = np.flatnonzero(scores >= self.score_threshold)
            if selected.size:
                all_scores.append(scores[selected])
                all_boxes.append(_distance_to_bbox(centers, boxes)[selected])
                all_landmarks.append(_distance_to_landmarks(centers, landmarks)[selected].reshape(-1, 5, 2))
        if not all_scores:
            return []

        scores = np.concatenate(all_scores).astype(np.float32)
        boxes = np.vstack(all_boxes).astype(np.float32) / scale
        landmarks = np.vstack(all_landmarks).astype(np.float32) / scale
        boxes[:, (0, 2)] = np.clip(boxes[:, (0, 2)], 0, source_width - 1)
        boxes[:, (1, 3)] = np.clip(boxes[:, (1, 3)], 0, source_height - 1)
        order = scores.argsort()[::-1]
        keep: list[int] = []
        while order.size:
            current = int(order[0])
            keep.append(current)
            rest = order[1:]
            if not rest.size:
                break
            overlap_x = np.maximum(0, np.minimum(boxes[current, 2], boxes[rest, 2]) - np.maximum(boxes[current, 0], boxes[rest, 0]))
            overlap_y = np.maximum(0, np.minimum(boxes[current, 3], boxes[rest, 3]) - np.maximum(boxes[current, 1], boxes[rest, 1]))
            intersection = overlap_x * overlap_y
            areas = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
            union = areas[current] + areas[rest] - intersection
            iou = np.divide(intersection, union, out=np.zeros_like(intersection), where=union > 0)
            order = rest[iou <= self.nms_threshold]
        return [DetectedFace(boxes[i], landmarks[i], float(scores[i])) for i in keep]
