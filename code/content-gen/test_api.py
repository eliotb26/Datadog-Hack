"""Quick test of image generation APIs"""
import os
import requests
from pathlib import Path
from dotenv import load_dotenv
from PIL import Image
from io import BytesIO

# Load env
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")

print(f"API Key found: {bool(HUGGINGFACE_API_KEY)}")
print(f"API Key starts with: {HUGGINGFACE_API_KEY[:10] if HUGGINGFACE_API_KEY else 'None'}...")

# Test FLUX
print("\n=== Testing FLUX.1-schnell ===")
API_URL = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"
headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}
payload = {"inputs": "a beautiful colorful bird in flight"}

response = requests.post(API_URL, headers=headers, json=payload, timeout=120)
print(f"Status: {response.status_code}")
print(f"Content-Type: {response.headers.get('content-type')}")
print(f"Content-Length: {len(response.content)}")

if response.status_code == 200:
    try:
        img = Image.open(BytesIO(response.content))
        print(f"✓ Image loaded successfully: {img.size}")
        img.save("test_flux.png")
        print("✓ Saved as test_flux.png")
    except Exception as e:
        print(f"✗ Failed to load image: {e}")
        print(f"Response text: {response.text[:500]}")
else:
    print(f"Response: {response.text[:500]}")

# Test Stable Diffusion XL
print("\n=== Testing Stable Diffusion XL ===")
API_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"
response = requests.post(API_URL, headers=headers, json=payload, timeout=120)
print(f"Status: {response.status_code}")
print(f"Content-Length: {len(response.content)}")

if response.status_code == 200:
    try:
        img = Image.open(BytesIO(response.content))
        print(f"✓ Image loaded successfully: {img.size}")
        img.save("test_sdxl.png")
        print("✓ Saved as test_sdxl.png")
    except Exception as e:
        print(f"✗ Failed to load image: {e}")
else:
    print(f"Response: {response.text[:500]}")
