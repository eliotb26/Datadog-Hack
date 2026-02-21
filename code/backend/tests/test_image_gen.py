"""
Standalone test for Gemini image generation.
Run from repo root:
  python -m code.backend.tests.test_image_gen
OR from code/ directory:
  python -m backend.tests.test_image_gen
"""
import asyncio
import sys
from pathlib import Path

# Allow running from repo root without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from backend.config import settings
from backend.integrations.gemini_media import generate_image_asset


async def main():
    print("=" * 60)
    print("Gemini Image Generation Test")
    print(f"  Model  : {settings.GEMINI_IMAGE_MODEL}")
    print(f"  API key: {'SET OK' if settings.gemini_api_key_set else 'MISSING'}")
    print(f"  Enabled: {settings.ENABLE_GEMINI_MEDIA}")
    print("=" * 60)

    if not settings.gemini_api_key_set:
        print("ERROR: GEMINI_API_KEY is not set. Check your .env file.")
        sys.exit(1)

    if not settings.ENABLE_GEMINI_MEDIA:
        print("ERROR: ENABLE_GEMINI_MEDIA is False. Set it to TRUE in .env.")
        sys.exit(1)

    prompt = (
        "A vibrant social media campaign banner for a modern tech startup. "
        "Bold typography, gradient background in purple and blue tones, "
        "professional and clean design, 16:9 landscape format."
    )
    print(f"\nPrompt: {prompt[:80]}…")
    print("\nGenerating image — this may take 10-30 seconds…")

    asset = await generate_image_asset(
        prompt=prompt,
        aspect_ratio="16:9",
        style_hint="modern, professional, digital art",
    )

    if asset:
        print("\n[SUCCESS]")
        print(f"   URL     : {asset.asset_url}")
        print(f"   Type    : {asset.asset_type}")
        print(f"   Provider: {asset.provider}")
        print(f"   Model   : {asset.model}")

        # Verify the file was actually saved
        media_dir = Path("./data/generated_media")
        fname = asset.asset_url.replace("/api/media/", "")
        fpath = media_dir / fname
        if fpath.exists():
            print(f"   File    : {fpath} ({fpath.stat().st_size:,} bytes)")
        else:
            print(f"   WARNING: File not found at expected path {fpath}")
    else:
        print("\n[FAILED] generate_image_asset returned None")
        print("Check logs above for the error details.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
