import cv2
from PIL import Image
from ollama import Client
import tempfile
import os

# === CONFIG ===
MODEL_NAME = "hardware"  # Your Ollama vision model (e.g., 'bakllava' or your custom 'hardware')
client = Client()

def capture_image():
    """Capture one frame from the default camera and return a PIL image."""
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("Camera not found.")
    ret, frame = cap.read()
    cap.release()
    if not ret:
        raise RuntimeError("Failed to capture image.")
    image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return Image.fromarray(image)

def run_vision_prompt(image: Image, prompt: str) -> str:
    """Send the image and prompt to the multimodal model and return the response."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        image.save(tmp.name)
        image_path = tmp.name

    try:
        response = client.generate(
            model=MODEL_NAME,
            prompt=prompt,
            images=[image_path],
        )
        return response["response"].strip()
    finally:
        os.remove(image_path)

if __name__ == "__main__":
    print("🔍 Capturing image...")
    img = capture_image()
    print("📡 Sending to model...")
    question = "What do you see in this image? Describe the scene."
    reply = run_vision_prompt(img, question)
    print(f"🤖 Jarvis (Vision Mode): {reply}")
