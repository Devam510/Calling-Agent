import os
import io
import wave
from backend.speech_to_text import transcribe, has_speech

def test():
    # 1. Test has_speech with exact 512 samples (1024 bytes)
    empty_audio = b"\x00" * 1024
    is_speaking = has_speech(empty_audio)
    print("Empty audio has speech:", is_speaking)

    # 2. Test transcribe
    # generate a small wav using empty audio, just to see it doesn't crash
    val = transcribe(empty_audio, "hi")
    print("Transcription of empty audio:", val)

if __name__ == "__main__":
    test()
