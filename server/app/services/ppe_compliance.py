"""Small position-aware PPE classifier for a single camera frame."""

from __future__ import annotations

from typing import Any

import cv2


PPE_ITEM_SPECS = {
    "helmet": {"display_name": "Helmet", "regions": ("head",)},
    "vest": {"display_name": "Vest", "regions": ("torso",)},
    "boots": {"display_name": "Boots", "regions": ("left_foot", "right_foot")},
}
MODEL_PPE_CLASSES = frozenset(PPE_ITEM_SPECS) | {"no_helmet", "no_boots"}
LABEL_ALIASES = {"boot": "boots"}


def _iou(a: list[float], b: list[float]) -> float:
    overlap = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - overlap
    return overlap / union if union > 0 else 0


class PersonTracker:
    def __init__(self) -> None:
        self.boxes: dict[int, list[float]] = {}
        self.next_id = 1

    def update(self, people: list[dict[str, Any]]) -> list[dict[str, Any]]:
        unused = set(self.boxes)
        for person in people:
            match = max(unused, key=lambda key: _iou(person["bbox"], self.boxes[key]), default=None)
            if match is None or _iou(person["bbox"], self.boxes[match]) < .3:
                match, self.next_id = self.next_id, self.next_id + 1
            else:
                unused.remove(match)
            person["track_id"] = match
            self.boxes[match] = person["bbox"]
        self.boxes = {person["track_id"]: person["bbox"] for person in people}
        return people


def _regions(box: list[float], width: int, height: int) -> tuple[dict[str, dict[str, Any]], bool]:
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    full = h >= height * .58 and x1 > 2 and y1 > 2 and x2 < width - 2 and y2 < height - 2
    raw = {
        "head": [x1 + .12*w, y1, x2 - .12*w, y1 + .30*h],
        "torso": [x1 + .12*w, y1 + .22*h, x2 - .12*w, y1 + .70*h],
        "left_hand": [x1 - .08*w, y1 + .25*h, x1 + .42*w, y1 + .72*h],
        "right_hand": [x1 + .58*w, y1 + .25*h, x2 + .08*w, y1 + .72*h],
        "left_foot": [x1, y1 + .70*h, x1 + .56*w, y2],
        "right_foot": [x1 + .44*w, y1 + .70*h, x2, y2],
    }
    clamp = lambda value, maximum: max(0., min(float(maximum), value))
    return ({name: {"bbox": [clamp(b[0], width), clamp(b[1], height), clamp(b[2], width), clamp(b[3], height)], "visible": full} for name, b in raw.items()}, full)


def _coverage(item: list[float], region: list[float]) -> float:
    overlap = max(0, min(item[2], region[2]) - max(item[0], region[0])) * max(0, min(item[3], region[3]) - max(item[1], region[1]))
    area = max(1, (item[2] - item[0]) * (item[3] - item[1]))
    center = ((item[0] + item[2]) / 2, (item[1] + item[3]) / 2)
    return overlap / area if region[0] <= center[0] <= region[2] and region[1] <= center[1] <= region[3] else 0


def analyze_compliance(people: list[dict[str, Any]], detections: list[dict[str, Any]], tracker: PersonTracker, frame_shape: tuple[int, ...], **_: Any) -> list[dict[str, Any]]:
    height, width = frame_shape[:2]
    tracked = tracker.update(people)
    for person in tracked:
        person["rois"], person["full_body_visible"] = _regions(person["bbox"], width, height)
        person["associations"] = {name: [] for name in PPE_ITEM_SPECS}

    for detection in detections:
        model_label = str(detection.get("label", "")).lower()
        label = LABEL_ALIASES.get(model_label.removeprefix("no_"), model_label.removeprefix("no_"))
        if label not in PPE_ITEM_SPECS:
            continue
        options = []
        for index, person in enumerate(tracked):
            for region in PPE_ITEM_SPECS[label]["regions"]:
                score = _coverage(detection["bbox"], person["rois"][region]["bbox"])
                if score >= .25:
                    options.append((score, index, region))
        if not options:
            continue
        score, index, region = max(options)
        row = {"bbox": detection["bbox"], "confidence": detection["confidence"], "association_score": round(score, 3), "region": region, "negative": model_label.startswith("no_")}
        tracked[index]["associations"][label].append(row)
        detection.update(track_id=tracked[index]["track_id"], worn=not row["negative"], region=region)

    for person in tracked:
        states = []
        for label, specification in PPE_ITEM_SPECS.items():
            rows = person["associations"][label]
            positive = [row for row in rows if not row["negative"]]
            negative = [row for row in rows if row["negative"]]
            found_regions = {row["region"] for row in positive}
            if negative:
                state, confidence = "NO", max(row["confidence"] for row in negative)
            elif set(specification["regions"]) <= found_regions:
                state, confidence = "YES", min(row["confidence"] for row in positive)
            elif person["full_body_visible"]:
                state, confidence = "NO", .65
            else:
                state, confidence = "UNKNOWN", 0
            person[label], person[f"{label}_confidence"] = state, round(float(confidence), 4)
            states.append(state)
        person["status"] = "VIOLATION" if "NO" in states else "COMPLIANT" if all(value == "YES" for value in states) else "UNKNOWN"
    return tracked


def annotate_compliance(image: Any, people: list[dict[str, Any]], detections: list[dict[str, Any]]) -> Any:
    for person in people:
        color = (68, 220, 90) if person["status"] == "COMPLIANT" else (50, 60, 235) if person["status"] == "VIOLATION" else (0, 190, 255)
        x1, y1, x2, y2 = map(int, person["bbox"])
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
        cv2.putText(image, person["status"], (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, .55, color, 2)
    for item in detections:
        if item.get("track_id") is None:
            continue
        color = (68, 220, 90) if item.get("worn") else (50, 60, 235)
        x1, y1, x2, y2 = map(int, item["bbox"])
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
        cv2.putText(image, item["label"], (x1, max(20, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, .45, color, 1)
    return image
