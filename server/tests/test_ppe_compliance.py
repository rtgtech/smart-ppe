import unittest

from app.services.ppe_compliance import PersonTracker, analyze_compliance


def detection(label, bbox, confidence=.9):
    return {"label": label, "bbox": bbox, "confidence": confidence}


class PpeComplianceTest(unittest.TestCase):
    def test_items_must_be_in_their_worn_regions(self):
        person = {"bbox": [100, 15, 300, 585], "confidence": .95}
        detections = [
            detection("helmet", [160, 10, 240, 105]),
            detection("vest", [130, 180, 270, 380]), detection("boots", [150, 500, 185, 585]),
            detection("boots", [215, 500, 250, 585]),
        ]
        result = analyze_compliance([person], detections, PersonTracker(), (600, 400, 3))[0]
        self.assertEqual(result["status"], "COMPLIANT")

    def test_carried_helmet_does_not_count_as_worn(self):
        person = {"bbox": [100, 15, 300, 585], "confidence": .95}
        result = analyze_compliance([person], [detection("helmet", [170, 250, 230, 310])], PersonTracker(), (600, 400, 3))[0]
        self.assertEqual(result["helmet"], "NO")

    def test_pair_items_require_both_sides(self):
        person = {"bbox": [100, 15, 300, 585], "confidence": .95}
        result = analyze_compliance([person], [detection("boots", [150, 500, 185, 585])], PersonTracker(), (600, 400, 3))[0]
        self.assertEqual(result["boots"], "NO")

    def test_cropped_person_stays_unknown(self):
        person = {"bbox": [0, 0, 220, 400], "confidence": .8}
        result = analyze_compliance([person], [], PersonTracker(), (600, 400, 3))[0]
        self.assertTrue(all(result[item] == "UNKNOWN" for item in ("helmet", "vest", "boots")))


if __name__ == "__main__":
    unittest.main()
