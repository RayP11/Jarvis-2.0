import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro
from pydub import AudioSegment
import os

# Initialize TTS model once
tts = Kokoro("kokoro-v1.0.onnx", "voices-v1.0.bin")

def generate_audio_mp3(text: str, wav_filename="output.wav", mp3_filename="output.mp3") -> str:
    """Generate TTS from text, save as WAV, convert to MP3, return MP3 path."""
    try:
        audio = tts.create(text, voice="bm_fable", speed=1.0)

        if not isinstance(audio, tuple) or not isinstance(audio[0], np.ndarray):
            print("Invalid audio output from Kokoro.")
            return None

        # Save as WAV
        sf.write(wav_filename, audio[0], 22050, format='WAV')
        print(f"✅ Saved WAV to {wav_filename}")

        # Convert to MP3
        sound = AudioSegment.from_wav(wav_filename)
        sound.export(mp3_filename, format="mp3")
        print(f"✅ Converted to MP3: {mp3_filename}")

        return mp3_filename

    except Exception as e:
        print(f"❌ Error generating audio: {e}")
        return None

if __name__ == "__main__":
    test_text = "Hey there Ray. Just testing that this file is being created properly and converted for texting."
    generate_audio_mp3(test_text)
