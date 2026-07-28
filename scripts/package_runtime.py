from __future__ import annotations

import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist" / "brainiall-0.1.0.difypkg"
RUNTIME_FILES = (
    "LICENSE",
    "PRIVACY.md",
    "README.md",
    "_assets/brainiall.png",
    "brainiall_api.py",
    "main.py",
    "manifest.yaml",
    "models/speech2text/brainiall-whisper.yaml",
    "models/speech2text/speech2text.py",
    "models/tts/brainiall-tts.yaml",
    "models/tts/tts.py",
    "provider/brainiall.py",
    "provider/brainiall.yaml",
    "pyproject.toml",
    "uv.lock",
)


def main() -> None:
    missing = [relative for relative in RUNTIME_FILES if not (ROOT / relative).is_file()]
    if missing:
        raise SystemExit(f"Missing runtime files: {', '.join(missing)}")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="brainiall-dify-runtime-") as temporary:
        stage = Path(temporary)
        for relative in RUNTIME_FILES:
            source = ROOT / relative
            destination = stage / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

        subprocess.run(
            ["dify", "plugin", "package", str(stage), "-o", str(OUTPUT)],
            check=True,
        )

    with zipfile.ZipFile(OUTPUT) as archive:
        packaged = set(archive.namelist())
    expected = set(RUNTIME_FILES)
    if packaged != expected:
        unexpected = sorted(packaged - expected)
        omitted = sorted(expected - packaged)
        raise SystemExit(
            f"Runtime package mismatch; unexpected={unexpected!r}, omitted={omitted!r}"
        )

    print(f"Validated runtime-only package: {OUTPUT}")


if __name__ == "__main__":
    main()
