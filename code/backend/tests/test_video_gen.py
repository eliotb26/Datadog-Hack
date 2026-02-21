"""
Standalone test for Gemini / Veo video generation.
Run from repo root:
  python -m code.backend.tests.test_video_gen
OR from code/ directory:
  python -m backend.tests.test_video_gen

NOTE: Video generation takes ~1-3 minutes. The test polls every 10s.
      Make sure ENABLE_VIDEO_GEN=TRUE in .env.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from backend.config import settings
from backend.integrations.gemini_media import generate_video_asset


async def main():
    print("=" * 60)
    print("Veo Video Generation Test")
    print(f"  Model    : {settings.GEMINI_VIDEO_MODEL}")
    print(f"  API key  : {'SET OK' if settings.gemini_api_key_set else 'MISSING'}")
    print(f"  Enabled  : {settings.ENABLE_GEMINI_MEDIA}")
    print(f"  Video ON : {settings.ENABLE_VIDEO_GEN}")
    print(f"  Timeout  : {settings.GEMINI_MEDIA_TIMEOUT_S}s")
    print("=" * 60)

    if not settings.gemini_api_key_set:
        print("ERROR: GEMINI_API_KEY is not set. Check your .env file.")
        sys.exit(1)

    if not settings.ENABLE_GEMINI_MEDIA:
        print("ERROR: ENABLE_GEMINI_MEDIA is False. Set it to TRUE in .env.")
        sys.exit(1)

    if not settings.ENABLE_VIDEO_GEN:
        print("ERROR: ENABLE_VIDEO_GEN is False. Set it to TRUE in .env.")
        sys.exit(1)

    prompt = (
        "A drone shot sweeping over a modern city skyline at golden hour. "
        "Cinematic motion, warm orange glow, skyscrapers reflecting the sunset. "
        "Smooth camera movement, professional quality."
    )
    print(f"\nPrompt: {prompt[:80]}…")
    print(f"\nGenerating video — polling every 10s (up to {settings.GEMINI_MEDIA_TIMEOUT_S}s)…")

    asset = await generate_video_asset(
        prompt=prompt,
        duration_s=8,
        aspect_ratio="16:9",
        style_hint="cinematic, drone footage",
    )

    if asset:
        print("\n[SUCCESS]")
        print(f"   URL     : {asset.asset_url}")
        print(f"   Type    : {asset.asset_type}")
        print(f"   Provider: {asset.provider}")
        print(f"   Model   : {asset.model}")

        media_dir = Path("./data/generated_media")
        fname = asset.asset_url.replace("/api/media/", "")
        fpath = media_dir / fname
        if fpath.exists():
            print(f"   File    : {fpath} ({fpath.stat().st_size:,} bytes)")
        else:
            print(f"   WARNING: File not found at expected path {fpath}")
    else:
        print("\n[FAILED] generate_video_asset returned None")
        print("Check logs above for the error details.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
