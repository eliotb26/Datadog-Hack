import os
import re
import argparse
from pathlib import Path

from dotenv import load_dotenv
from huggingface_hub import InferenceClient

DEFAULT_MODEL = "stabilityai/stable-diffusion-xl-base-1.0"

POST_PROMPT = """
Square Instagram post (1080x1080). Bright gradient background (yellow to purple), clean modern typography, fun and friendly.
Headline: “BECOME A SMARTER ADULT (IT’S NOT TOO LATE)”.
Bullets with icons: “Learn useful stuff”, “Meet cool people”, “Level up your life”.
Cute smiling brain mascot holding a coffee mug.
Bottom-left glossy button: “START FOR FREE”.
Bottom-right QR code card with label: “SCAN TO SIGN UP”.
Footer: “Limited spots - No exams, just good vibes”.
""".strip()


def slugify(text: str, max_len: int = 80) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return (text[:max_len] or "image")


def load_env_from_project_root() -> Path:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(env_path)
    return env_path


def get_hf_token() -> str | None:
    return os.getenv("HF_API_KEY") or os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACEHUB_API_TOKEN")


def main():
    env_path = load_env_from_project_root()
    token = get_hf_token()
    if not token:
        raise SystemExit(f"Token not found. Put HF_API_KEY in {env_path}")

    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", type=str, default=None, help="Custom prompt (optional)")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--out", type=str, default="generated_content/post.png")
    args = parser.parse_args()

    prompt = args.prompt or POST_PROMPT

    client = InferenceClient(api_key=token)
    image = client.text_to_image(prompt=prompt, model=args.model)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path)

    print(f"✅ Saved: {out_path.resolve()}")


if __name__ == "__main__":
    main()