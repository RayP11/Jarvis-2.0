import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro
import pygame
from io import BytesIO

# Initialize TTS model once
tts = Kokoro("kokoro-v1.0.onnx", "voices-v1.0.bin")

# Init pygame mixer for audio
pygame.mixer.init(frequency=22050)

def speak_text(text):
    try:
        audio = tts.create(text, voice="af_heart", speed=1.0)

        if isinstance(audio, tuple) and len(audio) > 1:
            audio_data = audio[0]
            if isinstance(audio_data, np.ndarray):
                # Save audio to a BytesIO stream
                audio_stream = BytesIO()
                sf.write(audio_stream, audio_data, 22050, format='WAV')
                audio_stream.seek(0)

                # Load and play from stream
                pygame.mixer.music.load(audio_stream)
                pygame.mixer.music.play()

                while pygame.mixer.music.get_busy():
                    pygame.time.Clock().tick(10)
            else:
                print("Audio is not a NumPy array.")
        else:
            print("Unexpected audio format from Kokoro.")
    except Exception as e:
        print(f"Exception in speak_text: {e}")

if __name__ == "__main__":
    text = "Good afternoon, Ray. Shall I begin prioritizing productivity, or are we embracing academic denial today?"
    speak_text(text)
