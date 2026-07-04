"""OpenCV face match: YuNet detector + SFace recognizer.

Real path (both images + ONNX models present): detect the largest face in each
image, align/crop, compute embeddings, cosine-match. Pass if score >= threshold.

Fallback (no images, e.g. synthetic passports with no photo): return a
deterministic verdict driven by the field checks so the demo oracle reproduces.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import numpy as np

from app.config import settings

_MODELS = Path(__file__).with_name("models")
_YUNET = _MODELS / "face_detection_yunet_2023mar.onnx"
_SFACE = _MODELS / "face_recognition_sface_2021dec.onnx"


def models_available() -> bool:
    return _YUNET.exists() and _SFACE.exists()


def _detect_largest(detector, img) -> Optional[np.ndarray]:
    h, w = img.shape[:2]
    detector.setInputSize((w, h))
    _, faces = detector.detect(img)
    if faces is None or len(faces) == 0:
        return None
    # largest by area (w*h at indices 2,3)
    return max(faces, key=lambda f: f[2] * f[3])


def match_faces(passport_image_path: str, selfie_path: str,
                crop_out_dir: Optional[str] = None) -> dict[str, Any]:
    """Real face match. Returns face_match_score, crops, passed, or a
    no_face_detected flag."""
    import cv2  # local import so the module loads without cv2 at import time

    if not models_available():
        return {"passed": False, "reason": "models_missing", "face_match_score": None}

    p_img = cv2.imread(passport_image_path)
    s_img = cv2.imread(selfie_path)
    if p_img is None or s_img is None:
        return {"passed": False, "reason": "image_unreadable", "face_match_score": None}

    detector = cv2.FaceDetectorYN.create(str(_YUNET), "", (320, 320))
    recognizer = cv2.FaceRecognizerSF.create(str(_SFACE), "")

    p_face = _detect_largest(detector, p_img)
    s_face = _detect_largest(detector, s_img)
    if p_face is None or s_face is None:
        return {"passed": False, "reason": "no_face_detected", "face_match_score": None}

    p_aligned = recognizer.alignCrop(p_img, p_face)
    s_aligned = recognizer.alignCrop(s_img, s_face)
    p_feat = recognizer.feature(p_aligned)
    s_feat = recognizer.feature(s_aligned)
    score = float(recognizer.match(p_feat, s_feat, cv2.FaceRecognizerSF_FR_COSINE))

    crops = {}
    if crop_out_dir:
        out = Path(crop_out_dir)
        out.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out / "passport_face.jpg"), p_aligned)
        cv2.imwrite(str(out / "selfie_face.jpg"), s_aligned)
        crops = {"passport_face_crop_path": str(out / "passport_face.jpg"),
                 "selfie_face_crop_path": str(out / "selfie_face.jpg")}

    return {
        "passed": score >= settings.face_match_threshold,
        "face_match_score": round(score, 4),
        "threshold": settings.face_match_threshold,
        "reason": None if score >= settings.face_match_threshold else "below_threshold",
        **crops,
    }


def fallback_match(field_checks_passed: bool) -> dict[str, Any]:
    """Deterministic verdict when no real images are available (synthetic
    passports). A synthetic 'match' score is reported above/below threshold to
    mirror the field-check outcome, keeping the oracle reproducible."""
    thr = settings.face_match_threshold
    score = round(thr + 0.25, 4) if field_checks_passed else round(thr - 0.15, 4)
    return {
        "passed": field_checks_passed,
        "face_match_score": score,
        "threshold": thr,
        "reason": None if field_checks_passed else "field_checks_failed",
        "fallback": True,
    }
