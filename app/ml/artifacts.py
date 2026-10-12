"""Saving and loading versioned model artifacts.

Artifacts are joblib files produced only by :mod:`app.ml.train`. Before an
artifact is loaded its SHA-256 digest is compared with the digest recorded in
the database at training time, so a tampered or foreign pickle file is refused.
"""
import hashlib
from pathlib import Path

import joblib

ARTIFACT_FORMAT = "trackwell-model-v1"


class ArtifactError(RuntimeError):
    """Raised when an artifact is missing, corrupted or not trusted."""


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def save_artifact(payload: dict, model_dir: Path, version: str) -> tuple[Path, str]:
    model_dir = Path(model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)
    path = model_dir / f"model_{version}.joblib"
    payload = dict(payload)
    payload["format"] = ARTIFACT_FORMAT
    joblib.dump(payload, path, compress=3)
    return path, sha256_of(path)


def load_artifact(path: Path, expected_sha256: str) -> dict:
    path = Path(path)
    if not path.exists():
        raise ArtifactError(f"Model artifact not found: {path}")
    actual = sha256_of(path)
    if actual != expected_sha256:
        raise ArtifactError(
            "Model artifact checksum does not match the value recorded at training time. "
            "The file was not loaded."
        )
    payload = joblib.load(path)
    if not isinstance(payload, dict) or payload.get("format") != ARTIFACT_FORMAT:
        raise ArtifactError("Model artifact has an unexpected format and was not loaded.")
    for key in ("pipeline", "feature_schema", "reference_values", "classes"):
        if key not in payload:
            raise ArtifactError(f"Model artifact is missing '{key}'.")
    return payload
