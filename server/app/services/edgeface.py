"""EdgeFace-S embedding model and ArcFace-compatible alignment."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np
import timm
import torch
from torch import nn


ARCFACE_112_TEMPLATE = np.array(
    [[38.2946, 51.6963], [73.5318, 51.5014], [56.0252, 71.7366],
     [41.5493, 92.3655], [70.7299, 92.2041]],
    dtype=np.float32,
)


def align_face(image: np.ndarray, landmarks: np.ndarray) -> np.ndarray:
    points = np.asarray(landmarks, dtype=np.float32)
    if points.shape != (5, 2) or not np.isfinite(points).all():
        raise ValueError("Five valid face landmarks are required")
    transform, _ = cv2.estimateAffinePartial2D(points, ARCFACE_112_TEMPLATE, method=cv2.LMEDS)
    if transform is None:
        raise ValueError("Face alignment failed")
    return cv2.warpAffine(image, transform, (112, 112), flags=cv2.INTER_LINEAR)


class _LowRankLinear(nn.Module):
    def __init__(self, source: nn.Linear) -> None:
        super().__init__()
        rank = max(2, min(source.in_features, source.out_features) // 2)
        self.linear1 = nn.Linear(source.in_features, rank, bias=False)
        self.linear2 = nn.Linear(rank, source.out_features, bias=source.bias is not None)

    def forward(self, value: Any) -> Any:
        return self.linear2(self.linear1(value))


def _factorize(module: nn.Module) -> None:
    for name, child in list(module.named_children()):
        if isinstance(child, nn.Linear) and "head" not in name:
            setattr(module, name, _LowRankLinear(child))
        else:
            _factorize(child)


class _EdgeFaceModel(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.model = timm.create_model("edgenext_small")
        self.model.reset_classifier(512)
        _factorize(self.model)

    def forward(self, value: Any) -> Any:
        return self.model(value)


class EdgeFaceEmbedder:
    def __init__(self, checkpoint_path: Path, device: str | None = None) -> None:
        if not checkpoint_path.is_file():
            raise FileNotFoundError(f"EdgeFace model not found: {checkpoint_path}")
        requested = (device or "").lower()
        if not requested or requested == "auto":
            requested = "cuda:0" if torch.cuda.is_available() else "cpu"
        elif requested.isdigit():
            requested = f"cuda:{requested}"
        if requested.startswith("cuda") and not torch.cuda.is_available():
            requested = "cpu"
        self.device = torch.device(requested)
        self.model = _EdgeFaceModel()
        state = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
        if isinstance(state, dict) and "state_dict" in state:
            state = state["state_dict"]
        normalized = {key.removeprefix("module."): value for key, value in state.items()}
        self.model.load_state_dict(normalized, strict=True)
        self.model.eval().to(self.device)

    def embed(self, aligned_bgr: np.ndarray) -> np.ndarray:
        rgb = cv2.cvtColor(aligned_bgr, cv2.COLOR_BGR2RGB)
        tensor = torch.from_numpy(np.ascontiguousarray(rgb)).permute(2, 0, 1)
        tensor = (tensor.to(self.device, dtype=torch.float32).unsqueeze(0) / 255.0 - 0.5) / 0.5
        with torch.inference_mode():
            vector = torch.nn.functional.normalize(self.model(tensor).reshape(-1), dim=0)
        return vector.cpu().numpy().astype(np.float32, copy=False)
