import os
import re
import argparse
from pathlib import Path

from dotenv import load_dotenv
from huggingface_hub import InferenceClient

DEFAULT_MODEL = "stabilityai/stable-diffusion-xl-base-1.0"


def slugify(text: str, max_len: int = 80) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return (text[:max_len] or "image")


def load_env_from_project_root() -> Path:
    # project-root/.env is outside code/, so: ../../.env from this file
    env_path = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(env_path)
    return env_path


def get_hf_token() -> str | None:
    return (
        os.getenv("HF_API_KEY")
        or os.getenv("HF_TOKEN")
        or os.getenv("HUGGINGFACEHUB_API_TOKEN")
    )


def main():
    env_path = load_env_from_project_root()
    token = get_hf_token()

    if not token:
        raise SystemExit(
            f"❌ Token not found.\nExpected .env at: {env_path}\nAdd: HF_API_KEY=hf_...\n"
        )

    parser = argparse.ArgumentParser(description="Generate an image using Hugging Face Inference Providers.")
    parser.add_argument("prompt", type=str)
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--out", type=str, default=None)
    args = parser.parse_args()

    client = InferenceClient(api_key=token)

    image = client.text_to_image(prompt=args.prompt, model=args.model)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        out_dir = Path(__file__).resolve().parent / "generated_content"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{slugify(args.prompt)}.png"

    image.save(out_path)
    print(f"✅ Saved: {out_path}")


if __name__ == "__main__":
    main()