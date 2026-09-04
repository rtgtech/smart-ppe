import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np

from app.services.edgeface import ARCFACE_112_TEMPLATE, align_face
from app.services.face_recognition import (
    EMBEDDING_MODEL_VERSION,
    LEGACY_EMBEDDING_MODEL_VERSION,
    FaceEngine,
    FaceRegistry,
)
from app.services.scrfd import SCRFDDetector, DetectedFace, _distance_to_bbox, _distance_to_landmarks


class FaceModelAdapterTest(unittest.TestCase):
    def test_scrfd_automatically_prefers_cuda(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scrfd.onnx"
            path.touch()
            with (
                patch(
                    "app.services.scrfd.ort.get_available_providers",
                    return_value=["CUDAExecutionProvider", "CPUExecutionProvider"],
                ),
                patch("app.services.scrfd.ort.InferenceSession") as create_session,
            ):
                session = create_session.return_value
                session.get_providers.return_value = ["CUDAExecutionProvider"]
                session.get_inputs.return_value = [SimpleNamespace(name="input")]
                session.get_outputs.return_value = [SimpleNamespace(name=str(index)) for index in range(9)]

                detector = SCRFDDetector(path)

            create_session.assert_called_once_with(
                str(path),
                providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
            )
            self.assertEqual(detector.provider, "CUDAExecutionProvider")

    def test_enrollment_ignores_small_background_faces(self):
        engine = object.__new__(FaceEngine)
        landmarks = np.zeros((5, 2), dtype=np.float32)
        primary = DetectedFace(np.array([50, 50, 250, 250], dtype=np.float32), landmarks, .99)
        distant = DetectedFace(np.array([300, 50, 350, 100], dtype=np.float32), landmarks, .9)
        with (
            patch.object(engine, "detect", return_value=[primary, distant]),
            patch.object(engine, "embedding_for_face", return_value=np.array([1., 0.], dtype=np.float32)),
        ):
            embedding = engine.enrollment_embedding([np.zeros((300, 400, 3), dtype=np.uint8)] * 5)
        np.testing.assert_allclose(embedding, [1., 0.])

    def test_scrfd_distance_decoding(self):
        centers = np.array([[10.0, 20.0]], dtype=np.float32)
        box = _distance_to_bbox(
            centers, np.array([[1.0, 2.0, 3.0, 4.0]], dtype=np.float32)
        )
        landmarks = _distance_to_landmarks(
            centers,
            np.array(
                [[1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]],
                dtype=np.float32,
            ),
        ).reshape(5, 2)

        np.testing.assert_allclose(box, [[9.0, 18.0, 13.0, 24.0]])
        np.testing.assert_allclose(
            landmarks,
            [[11.0, 22.0], [13.0, 24.0], [15.0, 26.0], [17.0, 28.0], [19.0, 30.0]],
        )

    def test_arcface_template_alignment_is_stable(self):
        image = np.zeros((112, 112, 3), dtype=np.uint8)
        cv2.circle(image, (56, 56), 10, (255, 255, 255), -1)
        aligned = align_face(image, ARCFACE_112_TEMPLATE.copy())
        self.assertEqual(aligned.shape, (112, 112, 3))
        difference = np.abs(aligned.astype(int) - image.astype(int))
        self.assertLess(float(np.mean(difference)), 0.1)

    def test_registry_never_compares_legacy_sface_with_edgeface(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "faces.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "profiles": {
                            "LEGACY": {
                                "person_id": "LEGACY",
                                "name": "Legacy Person",
                                "embedding": [1.0, 0.0],
                                "embedding_model": LEGACY_EMBEDDING_MODEL_VERSION,
                            },
                            "CURRENT": {
                                "person_id": "CURRENT",
                                "name": "Current Person",
                                "embedding": [0.0, 1.0],
                                "embedding_model": EMBEDDING_MODEL_VERSION,
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            registry = FaceRegistry(path)

            self.assertEqual(registry.count(), 2)
            self.assertEqual(registry.count(EMBEDDING_MODEL_VERSION), 1)
            self.assertEqual([item[0] for item in registry.embeddings()], ["CURRENT"])
            profiles = {item["person_id"]: item for item in registry.list_profiles()}
            self.assertTrue(profiles["LEGACY"]["requires_reenrollment"])
            self.assertFalse(profiles["CURRENT"]["requires_reenrollment"])


if __name__ == "__main__":
    unittest.main()
