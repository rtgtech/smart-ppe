"""Pose-guided PPE-to-person association for the entry camera pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2


Box = list[float]
HEAD_KEYPOINTS = (0, 1, 2, 3, 4)
LEFT_SHOULDER, RIGHT_SHOULDER = 5, 6
LEFT_HIP, RIGHT_HIP = 11, 12
LEFT_KNEE, RIGHT_KNEE = 13, 14
LEFT_ANKLE, RIGHT_ANKLE = 15, 16


def _area(box: Box) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def _intersection(first: Box, second: Box) -> float:
    return max(0.0, min(first[2], second[2]) - max(first[0], second[0])) * max(
        0.0, min(first[3], second[3]) - max(first[1], second[1])
    )


def box_iou(first: Box, second: Box) -> float:
    overlap = _intersection(first, second)
    union = _area(first) + _area(second) - overlap
    return overlap / union if union > 0 else 0.0


def _box_coverage(detection: Box, region: Box) -> float:
    area = _area(detection)
    return _intersection(detection, region) / area if area > 0 else 0.0


def _center_inside(box: Box, region: Box) -> bool:
    center_x = (box[0] + box[2]) / 2
    center_y = (box[1] + box[3]) / 2
    return region[0] <= center_x <= region[2] and region[1] <= center_y <= region[3]


def _clamp(box: Box, width: int, height: int) -> Box:
    return [
        round(max(0.0, min(float(width), box[0])), 1),
        round(max(0.0, min(float(height), box[1])), 1),
        round(max(0.0, min(float(width), box[2])), 1),
        round(max(0.0, min(float(height), box[3])), 1),
    ]


def _not_clipped(box: Box, width: int, height: int) -> bool:
    return box[0] > 0 and box[1] > 0 and box[2] < width and box[3] < height


def _point(keypoints: list[list[float]], index: int, threshold: float) -> list[float] | None:
    if index >= len(keypoints) or len(keypoints[index]) < 3:
        return None
    x, y, confidence = keypoints[index][:3]
    if float(confidence) < threshold:
        return None
    return [float(x), float(y), float(confidence)]


def _region(points: list[list[float]], pad_x: float, pad_top: float, pad_bottom: float, width: int, height: int) -> Box:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return _clamp(
        [min(xs) - pad_x, min(ys) - pad_top, max(xs) + pad_x, max(ys) + pad_bottom],
        width,
        height,
    )


@dataclass
class _Track:
    bbox: Box
    missed: int = 0


class PersonTracker:
    """Small per-WebSocket tracker that avoids sharing state between gate attempts."""

    def __init__(self, iou_threshold: float = 0.30, max_missed: int = 15) -> None:
        self.iou_threshold = iou_threshold
        self.max_missed = max_missed
        self._next_id = 1
        self._tracks: dict[int, _Track] = {}

    def update(self, people: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for track in self._tracks.values():
            track.missed += 1

        candidates: list[tuple[float, int, int]] = []
        for person_index, person in enumerate(people):
            for track_id, track in self._tracks.items():
                score = box_iou(person["bbox"], track.bbox)
                if score >= self.iou_threshold:
                    candidates.append((score, person_index, track_id))

        used_people: set[int] = set()
        used_tracks: set[int] = set()
        for _, person_index, track_id in sorted(candidates, reverse=True):
            if person_index in used_people or track_id in used_tracks:
                continue
            people[person_index]["track_id"] = track_id
            self._tracks[track_id] = _Track(list(people[person_index]["bbox"]))
            used_people.add(person_index)
            used_tracks.add(track_id)

        for person_index, person in enumerate(people):
            if person_index in used_people:
                continue
            track_id = self._next_id
            self._next_id += 1
            person["track_id"] = track_id
            self._tracks[track_id] = _Track(list(person["bbox"]))

        self._tracks = {
            track_id: track
            for track_id, track in self._tracks.items()
            if track.missed <= self.max_missed
        }
        return people


def _body_regions(
    person: dict[str, Any],
    frame_width: int,
    frame_height: int,
    keypoint_threshold: float,
    min_height_ratio: float,
    frame_margin_ratio: float,
) -> dict[str, dict[str, Any]]:
    x1, y1, x2, y2 = [float(value) for value in person["bbox"]]
    person_width = max(1.0, x2 - x1)
    person_height = max(1.0, y2 - y1)
    keypoints = person.get("keypoints") or []
    margin_x = frame_width * frame_margin_ratio
    margin_y = frame_height * frame_margin_ratio
    full_body_visible = (
        person_height / max(1, frame_height) >= min_height_ratio
        and x1 >= margin_x
        and y1 >= margin_y
        and x2 <= frame_width - margin_x
        and y2 <= frame_height - margin_y
    )

    head_points = [point for index in HEAD_KEYPOINTS if (point := _point(keypoints, index, keypoint_threshold))]
    if len(head_points) >= 2:
        head = _region(head_points, person_width * 0.10, person_height * 0.12, person_height * 0.05, frame_width, frame_height)
        head_source = "pose"
        head_confidence = sum(point[2] for point in head_points) / len(head_points)
    else:
        head = _clamp([x1, y1, x2, y1 + person_height * 0.28], frame_width, frame_height)
        head_source = "bbox"
        head_confidence = 0.65 if full_body_visible else 0.0

    torso_indices = (LEFT_SHOULDER, RIGHT_SHOULDER, LEFT_HIP, RIGHT_HIP)
    torso_points = [point for index in torso_indices if (point := _point(keypoints, index, keypoint_threshold))]
    has_shoulders = all(_point(keypoints, index, keypoint_threshold) for index in (LEFT_SHOULDER, RIGHT_SHOULDER))
    has_hip = any(_point(keypoints, index, keypoint_threshold) for index in (LEFT_HIP, RIGHT_HIP))
    if len(torso_points) >= 3 and has_shoulders and has_hip:
        torso = _region(torso_points, person_width * 0.10, person_height * 0.04, person_height * 0.07, frame_width, frame_height)
        torso_source = "pose"
        torso_confidence = sum(point[2] for point in torso_points) / len(torso_points)
    else:
        torso = _clamp(
            [x1 + person_width * 0.08, y1 + person_height * 0.18, x2 - person_width * 0.08, y1 + person_height * 0.68],
            frame_width,
            frame_height,
        )
        torso_source = "bbox"
        torso_confidence = 0.65 if full_body_visible else 0.0

    boot_regions: dict[str, Box] = {}
    boot_confidences: list[float] = []
    for side, knee_index, ankle_index, fallback_x1, fallback_x2 in (
        ("left", LEFT_KNEE, LEFT_ANKLE, x1, x1 + person_width / 2),
        ("right", RIGHT_KNEE, RIGHT_ANKLE, x1 + person_width / 2, x2),
    ):
        knee = _point(keypoints, knee_index, keypoint_threshold)
        ankle = _point(keypoints, ankle_index, keypoint_threshold)
        if knee and ankle:
            boot_regions[side] = _region(
                [knee, ankle], person_width * 0.10, person_height * 0.02, person_height * 0.08, frame_width, frame_height
            )
            boot_confidences.extend((knee[2], ankle[2]))
        else:
            boot_regions[side] = _clamp(
                [fallback_x1, y1 + person_height * 0.68, fallback_x2, y2], frame_width, frame_height
            )

    lower_points_present = all(
        _point(keypoints, index, keypoint_threshold)
        for index in (LEFT_KNEE, RIGHT_KNEE, LEFT_ANKLE, RIGHT_ANKLE)
    )
    boots_source = "pose" if lower_points_present else "bbox"
    boots_confidence = (
        sum(boot_confidences) / len(boot_confidences)
        if lower_points_present and boot_confidences
        else 0.65 if full_body_visible else 0.0
    )

    return {
        "head": {"bbox": head, "source": head_source, "visible": head_confidence > 0 and _not_clipped(head, frame_width, frame_height), "visibility_confidence": round(head_confidence, 4)},
        "torso": {"bbox": torso, "source": torso_source, "visible": torso_confidence > 0 and _not_clipped(torso, frame_width, frame_height), "visibility_confidence": round(torso_confidence, 4)},
        "left_boot": {"bbox": boot_regions["left"], "source": boots_source, "visible": boots_confidence > 0 and _not_clipped(boot_regions["left"], frame_width, frame_height), "visibility_confidence": round(boots_confidence, 4)},
        "right_boot": {"bbox": boot_regions["right"], "source": boots_source, "visible": boots_confidence > 0 and _not_clipped(boot_regions["right"], frame_width, frame_height), "visibility_confidence": round(boots_confidence, 4)},
    }


def _association_candidates(
    label: str,
    detection_box: Box,
    people: list[dict[str, Any]],
    overlap_threshold: float,
) -> list[tuple[float, int, str]]:
    candidates: list[tuple[float, int, str]] = []
    for person_index, person in enumerate(people):
        regions = person["rois"]
        if label == "helmet":
            names = ("head",)
        elif label == "vest":
            names = ("torso",)
        else:
            names = ("left_boot", "right_boot")

        scores = {name: _box_coverage(detection_box, regions[name]["bbox"]) for name in names}
        if label == "boots" and all(score >= 0.15 for score in scores.values()):
            combined_score = min(1.0, sum(scores.values()))
            candidates.append((combined_score, person_index, "both_boots"))
            continue
        for name, score in scores.items():
            if score >= overlap_threshold and _center_inside(detection_box, regions[name]["bbox"]):
                candidates.append((score, person_index, name))
    return candidates


def analyze_compliance(
    people: list[dict[str, Any]],
    ppe_detections: list[dict[str, Any]],
    tracker: PersonTracker,
    frame_shape: tuple[int, ...],
    *,
    keypoint_threshold: float = 0.35,
    overlap_threshold: float = 0.50,
    min_height_ratio: float = 0.60,
    frame_margin_ratio: float = 0.02,
) -> list[dict[str, Any]]:
    """Return per-person worn-PPE decisions for one frame."""
    frame_height, frame_width = frame_shape[:2]
    tracked = tracker.update(people)
    for person in tracked:
        person["rois"] = _body_regions(
            person,
            frame_width,
            frame_height,
            keypoint_threshold,
            min_height_ratio,
            frame_margin_ratio,
        )
        person["associations"] = {"helmet": [], "vest": [], "boots": []}

    for detection in ppe_detections:
        label = str(detection.get("label", "")).lower()
        if label not in {"helmet", "vest", "boots"}:
            continue
        candidates = _association_candidates(label, detection["bbox"], tracked, overlap_threshold)
        if not candidates:
            detection["worn"] = False
            continue
        score, person_index, region = max(candidates, key=lambda item: (item[0], -item[1]))
        association = {
            "bbox": list(detection["bbox"]),
            "detection_confidence": float(detection["confidence"]),
            "association_score": round(score, 4),
            "region": region,
        }
        tracked[person_index]["associations"][label].append(association)
        detection.update({"track_id": tracked[person_index]["track_id"], "region": region, "association_score": round(score, 4), "worn": True})

    results: list[dict[str, Any]] = []
    for person in tracked:
        result: dict[str, Any] = {
            "track_id": person["track_id"],
            "bbox": [round(float(value), 1) for value in person["bbox"]],
            "pose_confidence": round(float(person.get("confidence", 0.0)), 4),
            "rois": person["rois"],
            "associations": person["associations"],
        }
        item_states: list[str] = []
        for label, region_name in (("helmet", "head"), ("vest", "torso")):
            associations = person["associations"][label]
            if associations:
                best = max(associations, key=lambda row: row["detection_confidence"] * row["association_score"])
                state = "YES"
                confidence = best["detection_confidence"] * best["association_score"]
            elif person["rois"][region_name]["visible"]:
                state = "NO"
                confidence = person["rois"][region_name]["visibility_confidence"]
            else:
                state, confidence = "UNKNOWN", 0.0
            result[label] = state
            result[f"{label}_confidence"] = round(confidence, 4)
            item_states.append(state)

        boot_associations = person["associations"]["boots"]
        matched_sides: set[str] = set()
        for association in boot_associations:
            if association["region"] == "both_boots":
                matched_sides.update(("left_boot", "right_boot"))
            else:
                matched_sides.add(association["region"])
        if {"left_boot", "right_boot"}.issubset(matched_sides):
            result["boots"] = "YES"
            result["boots_confidence"] = round(
                min(row["detection_confidence"] * row["association_score"] for row in boot_associations), 4
            )
        elif person["rois"]["left_boot"]["visible"] and person["rois"]["right_boot"]["visible"]:
            result["boots"] = "NO"
            result["boots_confidence"] = round(
                min(
                    person["rois"]["left_boot"]["visibility_confidence"],
                    person["rois"]["right_boot"]["visibility_confidence"],
                ),
                4,
            )
        else:
            result["boots"], result["boots_confidence"] = "UNKNOWN", 0.0
        item_states.append(result["boots"])

        result["status"] = "VIOLATION" if "NO" in item_states else "COMPLIANT" if all(state == "YES" for state in item_states) else "UNKNOWN"
        results.append(result)
    return results


def annotate_compliance(image: Any, people: list[dict[str, Any]], detections: list[dict[str, Any]] | None = None) -> Any:
    colors = {"COMPLIANT": (70, 220, 90), "VIOLATION": (40, 40, 235), "UNKNOWN": (0, 190, 255)}
    roi_colors = {"head": (255, 200, 0), "torso": (255, 100, 180), "left_boot": (200, 160, 80), "right_boot": (200, 160, 80)}
    for person in people:
        color = colors[person["status"]]
        x1, y1, x2, y2 = (int(value) for value in person["bbox"])
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
        label = f"ID {person['track_id']} {person['status']} H:{person['helmet']} V:{person['vest']} B:{person['boots']}"
        cv2.putText(image, label, (x1, max(18, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.48, color, 2, cv2.LINE_AA)
        for name, region in person["rois"].items():
            rx1, ry1, rx2, ry2 = (int(value) for value in region["bbox"])
            cv2.rectangle(image, (rx1, ry1), (rx2, ry2), roi_colors[name], 1)
    for detection in detections or []:
        if str(detection.get("label", "")).lower() not in {"helmet", "vest", "boots"}:
            continue
        color = (70, 220, 90) if detection.get("worn") else (130, 130, 130)
        x1, y1, x2, y2 = (int(value) for value in detection["bbox"])
        suffix = f"worn by {detection['track_id']}" if detection.get("worn") else "not worn"
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
        cv2.putText(image, f"{detection['label']} {suffix}", (x1, max(18, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1, cv2.LINE_AA)
    return image
