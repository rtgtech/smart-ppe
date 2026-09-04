# Third-party face models

## EdgeFace

The EdgeFace-S gamma=0.5 architecture and checkpoint come from the official
EdgeFace repository at commit `ce86851cfc37979a9cd2558598d0e9bc592cbba3`:

<https://github.com/otroshi/edgeface>

EdgeFace is distributed under the BSD 3-Clause License. The reproduced license
is in [`third_party/EDGEFACE_LICENSE.txt`](third_party/EDGEFACE_LICENSE.txt).

## SCRFD / InsightFace

The SCRFD detector is `det_10g.onnx` from InsightFace's official `buffalo_l`
v0.7 release, renamed to `scrfd_10g_bnkps.onnx`. The local adapter is based on
the official SCRFD inference format and decoding logic:

<https://github.com/deepinsight/insightface>

The SCRFD source license is reproduced in
[`third_party/SCRFD_LICENSE.txt`](third_party/SCRFD_LICENSE.txt).

Important: InsightFace states that its downloaded pretrained models and the
training data behind them are limited to non-commercial research use. That
restriction applies to the bundled SCRFD checkpoint. Obtain an appropriate
commercial license from InsightFace or replace the checkpoint with one whose
training data and deployment rights fit the intended production use.

## Biometric deployment

Model licenses do not grant permission to collect or process biometric data.
Deployment owners remain responsible for consent or another lawful basis,
retention and deletion controls, access restrictions, security, auditability,
human review, and jurisdiction-specific biometric/privacy requirements.
