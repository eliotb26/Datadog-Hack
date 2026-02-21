import argparse
import subprocess
from pathlib import Path


def run(cmd: list[str]) -> None:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"Command failed:\n{' '.join(cmd)}\n\nSTDERR:\n{p.stderr}")


def make_ken_burns_3s(input_img: Path, output_mp4: Path, seconds: float = 3.0, fps: int = 30):
    """
    Creates a 3s MP4 with a gentle zoom-in (Ken Burns effect).
    Works with any single image.
    """
    frames = int(seconds * fps)

    # Zoom from 1.0 to ~1.10 over the clip
    # scale to even dimensions for h264
    vf = (
        f"scale=trunc(iw/2)*2:trunc(ih/2)*2,"
        f"zoompan=z='1+0.10*on/{frames}':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2'"
        f":d={frames}:s=1024x1024:fps={fps}"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-loop", "1",
        "-i", str(input_img),
        "-vf", vf,
        "-t", str(seconds),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_mp4),
    ]
    run(cmd)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=str, help="Input image path (png/jpg)")
    parser.add_argument("--out", type=str, default=None, help="Output mp4 path")
    parser.add_argument("--seconds", type=float, default=3.0)
    parser.add_argument("--fps", type=int, default=30)
    args = parser.parse_args()

    img = Path(args.image).expanduser().resolve()
    if not img.exists():
        raise SystemExit(f"Image not found: {img}")

    out = Path(args.out).expanduser().resolve() if args.out else img.with_suffix(".mp4")

    make_ken_burns_3s(img, out, seconds=args.seconds, fps=args.fps)
    print(f"✅ Saved: {out}")


if __name__ == "__main__":
    main()