"""
Simple image generator using diffusers library (runs locally)
No API keys needed - downloads model once and runs on your machine
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Output directory
OUTPUT_DIR = Path(__file__).parent / "generated_content"
OUTPUT_DIR.mkdir(exist_ok=True)

def enhance_prompt(prompt: str) -> str:
    """Use Gemini to enhance prompt"""
    import requests
    
    if not GEMINI_API_KEY:
        return prompt
    
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    payload = {
        "contents": [{
            "parts": [{
                "text": f"Enhance this image prompt with vivid details: {prompt}\n\nReturn only the enhanced prompt, nothing else."
            }]
        }]
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            result = response.json()
            return result['candidates'][0]['content']['parts'][0]['text'].strip()
    except:
        pass
    
    return prompt

def generate_image(prompt: str):
    """Generate image using local Stable Diffusion"""
    try:
        from diffusers import StableDiffusionPipeline
        import torch
        
        print("Loading Stable Diffusion model (first time will download ~4GB)...")
        
        # Use smaller, faster model
        model_id = "runwayml/stable-diffusion-v1-5"
        
        # Check if MPS (Apple Silicon) is available
        if torch.backends.mps.is_available():
            device = "mps"
            print("Using Apple Silicon GPU")
        elif torch.cuda.is_available():
            device = "cuda"
            print("Using NVIDIA GPU")
        else:
            device = "cpu"
            print("Using CPU (will be slower)")
        
        pipe = StableDiffusionPipeline.from_pretrained(
            model_id,
            torch_dtype=torch.float16 if device != "cpu" else torch.float32
        )
        pipe = pipe.to(device)
        
        # Enhance prompt
        print(f"\nOriginal prompt: {prompt}")
        enhanced = enhance_prompt(prompt)
        print(f"Enhanced prompt: {enhanced}\n")
        
        print("Generating image...")
        image = pipe(enhanced, num_inference_steps=30).images[0]
        
        # Save
        output_path = OUTPUT_DIR / f"image_{len(list(OUTPUT_DIR.glob('image_*.png')))}.png"
        image.save(output_path)
        print(f"\n✓ Image saved to: {output_path}")
        
    except ImportError:
        print("\n✗ diffusers library not installed!")
        print("\nInstall with:")
        print("  pip install diffusers transformers accelerate torch torchvision")
        print("\nNote: This will download ~4GB on first run")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python simple_generator.py 'your prompt here'")
        print("Example: python simple_generator.py 'a beautiful bird in flight'")
        sys.exit(1)
    
    prompt = sys.argv[1]
    
    print("="*60)
    print("OnlyGen - Local Image Generator")
    print("="*60)
    
    generate_image(prompt)
    
    print("\n" + "="*60)
    print("Done!")
    print("="*60)
