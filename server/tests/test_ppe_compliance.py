import unittest

import cv2
import numpy as np

from app.api.v1.routes.entry import _frame_evidence
from app.services.ppe_compliance import PersonTracker, analyze_compliance


FRAME_SHAPE = (600, 400, 3)


def posed_person(x_offset=0):
    keypoints = [[0, 0, 0] for _ in range(17)]
    values = {
        0: [200, 80, .95], 1: [190, 70, .92], 2: [210, 70, .93],
        3: [175, 80, .88], 4: [225, 80, .89],
        5: [160, 170, .96], 6: [240, 170, .95],
        7: [140, 260, .93], 8: [260, 260, .93],
        9: [130, 350, .91], 10: [270, 350, .91],
        11: [175, 330, .94], 12: [225, 330, .93],
        13: [175, 440, .91], 14: [225, 440, .92],
        15: [170, 550, .90], 16: [230, 550, .90],
    }
    for index, value in values.items():
        keypoints[index] = [value[0] + x_offset, value[1], value[2]]
    return {"bbox": [100 + x_offset, 15, 300 + x_offset, 585], "confidence": .97, "keypoints": keypoints}


def detection(label, bbox, confidence=.9):
    return {"label": label, "bbox": bbox, "confidence": confidence, "class_id": 0}


class PpeComplianceTest(unittest.TestCase):
    def analyze(self, people, detections, tracker=None, shape=FRAME_SHAPE):
        return analyze_compliance(people, detections, tracker or PersonTracker(), shape)

    def test_correctly_positioned_items_are_compliant(self):
        result = self.analyze(
            [posed_person()],
            [
                detection("glove", [108, 315, 158, 375], .91),
                detection("glove", [242, 315, 292, 375], .90),
                detection("goggles", [175, 50, 225, 82], .94),
                detection("helmet", [160, 10, 240, 105], .95),
                detection("mask", [175, 80, 225, 108], .93),
                detection("shoes", [150, 500, 195, 585], .90),
                detection("shoes", [205, 500, 250, 585], .89),
            ],
        )[0]
        self.assertTrue(all(result[name] == "YES" for name in ("glove", "goggles", "helmet", "mask", "shoes")))
        self.assertEqual(result["status"], "COMPLIANT")

    def test_carried_and_background_ppe_do_not_count(self):
        detections = [
            detection("helmet", [170, 250, 230, 310]),
            detection("mask", [305, 180, 390, 350]),
        ]
        result = self.analyze([posed_person()], detections)[0]
        self.assertEqual(result["helmet"], "NO")
        self.assertEqual(result["mask"], "NO")
        self.assertEqual(result["status"], "VIOLATION")
        self.assertTrue(all(row.get("worn") is False for row in detections))

    def test_one_visible_shoe_is_not_a_complete_pair(self):
        result = self.analyze(
            [posed_person()],
            [detection("shoes", [150, 500, 195, 585])],
        )[0]
        self.assertEqual(result["shoes"], "NO")
        self.assertEqual(len(result["associations"]["shoes"]), 1)

    def test_explicit_negative_class_overrides_positive_detection(self):
        detections = [
            detection("goggles", [175, 50, 225, 82], .95),
            detection("no_goggles", [175, 50, 225, 82], .80),
        ]
        result = self.analyze(
            [posed_person()],
            detections,
        )[0]
        self.assertEqual(result["goggles"], "NO")
        self.assertEqual(len(result["associations"]["goggles"]), 2)
        self.assertFalse(detections[1]["worn"])

    def test_cropped_low_confidence_person_is_unknown(self):
        person = {"bbox": [0, 0, 220, 400], "confidence": .8, "keypoints": [[0, 0, 0] for _ in range(17)]}
        result = self.analyze([person], [])[0]
        self.assertTrue(all(result[name] == "UNKNOWN" for name in ("glove", "goggles", "helmet", "mask", "shoes")))
        self.assertEqual(result["status"], "UNKNOWN")

    def test_full_body_bbox_fallback_can_support_negative_evidence(self):
        person = {"bbox": [50, 20, 350, 580], "confidence": .8, "keypoints": [[0, 0, 0] for _ in range(17)]}
        result = self.analyze([person], [])[0]
        self.assertTrue(all(result[name] == "NO" for name in ("glove", "goggles", "helmet", "mask", "shoes")))
        self.assertEqual(result["rois"]["head"]["source"], "bbox")

    def test_detection_is_assigned_to_only_the_best_person(self):
        people = [posed_person(-105), posed_person(95)]
        detections = [detection("helmet", [250, 10, 340, 105])]
        results = self.analyze(people, detections)
        self.assertEqual(results[0]["helmet"], "NO")
        self.assertEqual(results[1]["helmet"], "YES")
        self.assertEqual(detections[0]["track_id"], results[1]["track_id"])

    def test_tracker_keeps_id_and_expires_missing_tracks(self):
        tracker = PersonTracker(iou_threshold=.3, max_missed=1)
        first = tracker.update([{"bbox": [10, 10, 100, 200]}])[0]["track_id"]
        second = tracker.update([{"bbox": [15, 12, 105, 202]}])[0]["track_id"]
        self.assertEqual(first, second)
        tracker.update([])
        tracker.update([])
        replacement = tracker.update([{"bbox": [15, 12, 105, 202]}])[0]["track_id"]
        self.assertNotEqual(first, replacement)

    def test_entry_frame_evidence_uses_anatomical_results(self):
        persons = self.analyze(
            [posed_person()],
            [
                detection("glove", [108, 315, 158, 375]),
                detection("glove", [242, 315, 292, 375]),
                detection("goggles", [175, 50, 225, 82]),
                detection("helmet", [160, 10, 240, 105]),
                detection("mask", [175, 80, 225, 108]),
                detection("shoes", [150, 500, 195, 585]),
                detection("shoes", [205, 500, 250, 585]),
            ],
        )
        checkerboard = ((np.indices(FRAME_SHAPE[:2]).sum(axis=0) % 2) * 255).astype(np.uint8)
        image = cv2.cvtColor(checkerboard, cv2.COLOR_GRAY2BGR)
        ok, encoded = cv2.imencode(".jpg", image)
        self.assertTrue(ok)
        faces = [{"bbox": [175, 45, 225, 115], "recognized": True, "person_id": "WORKER1", "similarity": .9}]
        evidence = _frame_evidence(encoded.tobytes(), persons, faces)
        self.assertTrue(evidence["framing_valid"])
        self.assertTrue(evidence["quality_valid"])
        self.assertTrue(all(
            evidence["visual"][name]["state"] == "POSITIVE"
            for name in ("Gloves", "Goggles", "Helmet", "Mask", "Shoes")
        ))
        self.assertEqual(evidence["visual"]["Helmet"]["track_id"], persons[0]["track_id"])


if __name__ == "__main__":
    unittest.main()
