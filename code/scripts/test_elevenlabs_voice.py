#!/usr/bin/env python3
"""Standalone script to test ElevenLabs voice agent.

Run from repo root after adding ELEVENLABS_API_KEY to .env:

    python code/scripts/test_elevenlabs_voice.py

Or from code/ directory:

    python scripts/test_elevenlabs_voice.py

Output: saves test audio to code/backend/data/elevenlabs_test.mp3
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Add backend to path and load .env from repo root
_repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_repo_root / "code" / "backend"))

_env = _repo_root / ".env"
if _env.exists():
    from dotenv import load_dotenv
    load_dotenv(_env)

from integrations.elevenlabs_voice import ElevenLabsVoiceClient


def main() -> int:
    print("ElevenLabs Voice Agent — standalone test")
    print("-" * 50)

    client = ElevenLabsVoiceClient()
    if not client.is_configured:
        print("ERROR: ELEVENLABS_API_KEY is not set. Add it to .env (see .env.template)")
        return 1

    output_dir = _repo_root / "code" / "backend" / "data"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "elevenlabs_test.mp3"

    text = "Hello. This is a test of the ElevenLabs voice agent. If you hear this, the integration is working."
    print(f"Converting: {text}")

    try:
        data = client.text_to_speech(text, output_path=str(output_path))
        print(f"Success! Generated {len(data)} bytes")
        print(f"Saved to: {output_path}")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
