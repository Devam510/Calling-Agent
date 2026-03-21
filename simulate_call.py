"""
simulate_call.py — PC Voice Simulator for the Calling Agent

Runs the full AI pipeline (STT -> LLM -> TTS) using your computer's mic/speaker
instead of the Android gateway. Great for testing prompt latency and Hindi voice!
"""

import asyncio
import logging
import queue
import time
import sounddevice as sd
import numpy as np

from backend.config import settings
from backend.speech_to_text import SpeechToText
from backend.text_to_speech import TextToSpeech
from backend.conversation_engine import ConversationEngine
from backend.models import Lead

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("simulator")

SAMPLE_RATE = settings.audio_sample_rate
CHUNK_SIZE = int(SAMPLE_RATE * 0.1)  # 100ms chunks

# Globals for playback control
tts_audio_queue: asyncio.Queue = asyncio.Queue()
playback_active = False

def audio_callback(indata, frames, time, status, q: queue.Queue):
    """Callback for sounddevice microphone input."""
    if status:
        logger.warning(status)
    q.put(bytes(indata))


async def pc_playback_worker():
    """Reads PCM audio from queue and plays to PC speakers."""
    global playback_active
    with sd.RawOutputStream(samplerate=SAMPLE_RATE, blocksize=CHUNK_SIZE,
                            channels=1, dtype='int16') as stream:
        while True:
            chunk = await tts_audio_queue.get()
            if chunk is None:
                break
            # Play audio block
            stream.write(chunk)


async def main():
    logger.info("Initializing Models... (Whisper, Groq, Piper)")
    stt = SpeechToText()
    tts = TextToSpeech()
    stt.start()

    lead = Lead(id="sim_1", phone="1234567890", company_name="Mock Company", owner_name="Amit", city="Delhi")
    engine = ConversationEngine(lead)

    mic_queue: queue.Queue = queue.Queue()
    
    # Start speaker thread
    playback_task = asyncio.create_task(pc_playback_worker())

    logger.info("Connecting to microphone...")
    with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=CHUNK_SIZE,
                           channels=1, dtype='int16', callback=lambda i,f,t,s: audio_callback(i,f,t,s, mic_queue)):
        
        logger.info("=== PC SIMULATOR RUNNING ===")
        print("\n\t🎤 Talk into your PC mic now!\n\t(Press Ctrl+C to exit)\n")

        # Drain empty noise
        while not mic_queue.empty(): mic_queue.get()
        
        try:
            while True:
                # 1. Capture Mic
                mic_chunk = await asyncio.get_event_loop().run_in_executor(None, mic_queue.get)
                
                # 2. Push to STT
                transcript = stt.process_chunk(mic_chunk)
                if transcript:
                    print(f"\n[Customer]: {transcript}")
                    
                    # 3. LLM Generate
                    print("[Agent thinking...]", end="", flush=True)
                    start_t = time.time()
                    bot_text = ""
                    
                    tts_stream = tts.synthesize_stream(engine.generate_reply_stream(transcript))
                    
                    first_audio = True
                    async for pcm_chunk, sent_text in tts_stream:
                        if first_audio:
                            print(f"\n⚡ Response time: {time.time()-start_t:.2f}s")
                            print(f"[Agent]: {sent_text}", end="", flush=True)
                            first_audio = False
                        else:
                            print(f" {sent_text}", end="", flush=True)
                        
                        await tts_audio_queue.put(pcm_chunk)
                    
                    print("\n")
                    
                await asyncio.sleep(0.01)

        except KeyboardInterrupt:
            logger.info("Stopping...")
        finally:
            stt.stop()
            await tts_audio_queue.put(None)
            await playback_task


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
