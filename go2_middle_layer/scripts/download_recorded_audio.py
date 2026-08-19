#!/usr/bin/env python3
"""
Download pre-recorded DOG audio files for RecordedAudio enum.
Sources: OpenGameArt.org (CC0) - dog barks, growls, whimpers from dog.7z pack.
Run from project root: python scripts/download_recorded_audio.py
Use --force to replace existing files.
Requires: py7zr (pip install py7zr)
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Target directory (SPEAKER_AUDIO_DIR default)
AUDIO_DIR = Path(__file__).resolve().parent.parent / "src" / "resources" / "sound" / "dog"

# dog.7z from OpenGameArt (pauliuw) - 9 dog sounds: barks, growls, squalling
DOG_7Z_URL = "https://opengameart.org/sites/default/files/dog.7z"

# Map RecordedAudio -> path inside dog.7z (Dog/...)
DOG_7Z_MAPPING = {
    "bark": "Dog/Dog Bark 1.wav",
    "happy": "Dog/Dog Bark 2.wav",
    "sad": "Dog/Sad Dog 1.wav",
    "alert": "Dog/Dog Bark 3.wav",
    "greeting": "Dog/Dog Bark.wav",
    "goodbye": "Dog/Dog 2.wav",
    "acknowledge": "Dog/Dog Bark.wav",
    "error": "Dog/Dog 1.wav",
    "confused": "Dog/Sad Dog.wav",
}

# Fallback: direct WAV if py7zr unavailable
FALLBACK_URLS = {
    "bark": "https://opengameart.org/sites/default/files/dog_barking_mono.wav",
    "happy": "https://opengameart.org/sites/default/files/dog_barking.wav",
    "sad": "https://opengameart.org/sites/default/files/dog_barking_mono.wav",
    "alert": "https://opengameart.org/sites/default/files/dog_barking_mono.wav",
    "greeting": "https://opengameart.org/sites/default/files/dog_barking_mono.wav",
    "goodbye": "https://opengameart.org/sites/default/files/dog_barking_mono.wav",
    "acknowledge": "https://opengameart.org/sites/default/files/dog_barking_mono.wav",
    "error": "https://opengameart.org/sites/default/files/dog_barking_mono.wav",
    "confused": "https://opengameart.org/sites/default/files/dog_barking_mono.wav",
}


def download_file(url: str, dest: Path) -> bool:
    """Download file using curl."""
    try:
        result = subprocess.run(
            ["curl", "-sL", "-o", str(dest), url],
            capture_output=True,
            timeout=90,
        )
        return result.returncode == 0 and dest.exists() and dest.stat().st_size > 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def extract_dog_7z(audio_dir: Path, force: bool) -> tuple[int, int, int]:
    """Extract dog.7z and copy mapped files. Returns (ok, skip, fail)."""
    try:
        import py7zr
    except ImportError:
        print("  [warn] py7zr not installed. Run: pip install py7zr")
        return 0, 0, 9  # all fail, will use fallback

    ok, skip, fail = 0, 0, 0
    zip_path = audio_dir / "_dog.7z"

    if not zip_path.exists() or force:
        print("  [downloading] dog.7z ...")
        if not download_file(DOG_7Z_URL, zip_path):
            print("  [fail] dog.7z download failed")
            return 0, 0, 9
    else:
        print("  [using] cached dog.7z")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        try:
            with py7zr.SevenZipFile(zip_path, "r") as zf:
                zf.extractall(tmp)
        except Exception as e:
            print(f"  [fail] extract: {e}")
            return 0, 0, 9

        for name, inner_path in DOG_7Z_MAPPING.items():
            dest = audio_dir / f"{name}.wav"
            if dest.exists() and not force:
                print(f"  [skip] {name}.wav")
                skip += 1
                continue

            src = tmp / inner_path
            if not src.exists():
                print(f"  [fail] {name}.wav ({inner_path} not found)")
                fail += 1
                continue

            shutil.copy2(src, dest)
            print(f"  [ok] {name}.wav")
            ok += 1

    return ok, skip, fail


def fallback_download(audio_dir: Path, force: bool) -> tuple[int, int, int]:
    """Fallback: direct WAV download when py7zr unavailable."""
    ok, skip, fail = 0, 0, 0
    for name, url in FALLBACK_URLS.items():
        dest = audio_dir / f"{name}.wav"
        if dest.exists() and not force:
            print(f"  [skip] {name}.wav")
            skip += 1
            continue

        tmp = audio_dir / f"_tmp_{name}"
        print(f"  [downloading] {name}.wav ...")
        if not download_file(url, tmp):
            print(f"  [fail] {name}.wav")
            if tmp.exists():
                tmp.unlink()
            fail += 1
            continue

        tmp.rename(dest)
        print(f"  [ok] {name}.wav")
        ok += 1
    return ok, skip, fail


def main() -> int:
    parser = argparse.ArgumentParser(description="Download dog sound effects for RecordedAudio")
    parser.add_argument("--force", action="store_true", help="Replace existing files")
    parser.add_argument("--fallback", action="store_true", help="Skip dog.7z, use direct WAV URLs")
    args = parser.parse_args()

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    if args.fallback:
        print("Using fallback (direct WAV downloads)...")
        ok, skip, fail = fallback_download(AUDIO_DIR, args.force)
    else:
        print("Extracting from dog.7z (OpenGameArt pauliuw pack)...")
        ok, skip, fail = extract_dog_7z(AUDIO_DIR, args.force)
        if fail == 9 and ok == 0:
            print("\nFalling back to direct WAV downloads...")
            ok, skip, fail = fallback_download(AUDIO_DIR, args.force)

    print(f"\nDone: {ok} downloaded, {skip} skipped, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
