from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
TEMPLATE_DIR = ROOT / "examples" / "transcription"


def load_template(name: str) -> dict:
    return json.loads((TEMPLATE_DIR / name).read_text(encoding="utf-8"))


def test_request_template_has_no_literal_secret_and_fixed_origin() -> None:
    template = load_template("youtube-subtitles-srt-request.json")
    assert template["security"]["neverCommitSecrets"] is True
    assert template["request"]["url"] == (
        "https://api.brainiall.com/v1/whisper/transcribe"
    )
    assert "${BRAINIALL_API_KEY}" in template["request"]["headers"]["Authorization"]
    assert "brn_test_should_never_appear" not in json.dumps(template)


def test_quality_gate_requires_manual_review_and_no_publish() -> None:
    template = load_template("youtube-subtitles-srt-quality-gate.json")
    check_ids = {check["id"] for check in template["checks"]}
    assert {"valid-time-order", "non-empty-text", "utf8-text", "human-review"} <= check_ids
    assert template["checks"][-1]["rule"] == "reviewerAccepted == true"
    assert "manual" in template["output"]["pass"]
