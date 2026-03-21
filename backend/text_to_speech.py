import os
import io
import wave
import asyncio
from pathlib import Path
from typing import AsyncIterator
import logging
from piper import PiperVoice
import soundfile as sf
import numpy as np
import huggingface_hub

logger = logging.getLogger(__name__)

class TextToSpeech:
    """
    Wrapper for Piper TTS producing 16kHz PCM audio efficiently.
    Downloads the model automatically from HuggingFace on first use.
    """
    
    def __init__(self, voice_model: str = "hi_IN-priyamvada-medium"):
        self.voice_model = voice_model
        
        # Determine paths
        models_dir = Path("models/tts")
        models_dir.mkdir(parents=True, exist_ok=True)
        
        self.onnx_path = models_dir / f"{self.voice_model}.onnx"
        self.json_path = models_dir / f"{self.voice_model}.onnx.json"
        
        self._ensure_model_downloaded()
        
        # Load Piper model
        logger.info(f"Loading Piper voice from {self.onnx_path}")
        self.voice = PiperVoice.load(str(self.onnx_path), config_path=str(self.json_path))
        
    def _ensure_model_downloaded(self):
        """Downloads the ONNX model and config from huggingface."""
        if self.onnx_path.exists() and self.json_path.exists():
            return
            
        logger.info(f"Downloading Piper TTS model '{self.voice_model}'...")
        
        try:
            # Format: hi/hi_IN/swara/medium/hi_IN-swara-medium.onnx
            parts = self.voice_model.split("-")
            if len(parts) == 3:
                family, speaker, quality = parts
                lang = family.split("_")[0]
                
                hf_repo = "rhasspy/piper-voices"
                base_path = f"{lang}/{family}/{speaker}/{quality}/{self.voice_model}"
                
                onnx_dl = huggingface_hub.hf_hub_download(
                    repo_id=hf_repo,
                    filename=f"{base_path}.onnx",
                    local_dir=str(self.onnx_path.parent),
                    local_dir_use_symlinks=False
                )
                json_dl = huggingface_hub.hf_hub_download(
                    repo_id=hf_repo,
                    filename=f"{base_path}.onnx.json",
                    local_dir=str(self.json_path.parent),
                    local_dir_use_symlinks=False
                )
                
                # Move from local_dir structure to the flat models/tts dir
                dl_onnx = Path(onnx_dl)
                dl_json = Path(json_dl)
                if dl_onnx != self.onnx_path:
                    dl_onnx.rename(self.onnx_path)
                if dl_json != self.json_path:
                    dl_json.rename(self.json_path)
                    
                # Clean up empty dirs if moved
                dl_dir = dl_onnx.parent
                if dl_dir != self.onnx_path.parent:
                    import shutil
                    # Just remove the root language folder inside models/tts
                    lang_dir = self.onnx_path.parent / lang
                    if lang_dir.exists():
                        shutil.rmtree(lang_dir, ignore_errors=True)
                        
                logger.info("TTS model downloaded successfully.")
            else:
                raise ValueError(f"Unsupported voice model format: {self.voice_model}")
        except Exception as e:
            logger.error(f"Failed to download TTS model: {e}")
            raise
            
    def synthesize(self, text: str) -> bytes:
        """
        Synthesize text to raw PCM 16kHz mono bytes.
        """
        # PiperVoice doesn't have a direct "to_bytes". We use an in-memory wav.
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)
            self.voice.synthesize(text, wav_file)
            
        buf.seek(0)
        with wave.open(buf, 'rb') as wav_file:
            return wav_file.readframes(wav_file.getnframes())

    async def synthesize_streaming(self, text: str) -> AsyncIterator[bytes]:
        """
        Streaming synthesis for lowest time-to-first-byte (TTFB).
        """
        loop = asyncio.get_running_loop()
        queue = asyncio.Queue()
        done_event = asyncio.Event()
        
        def _sync_worker():
            try:
                # synthesize yields AudioChunk objects per sentence
                for audio_chunk in self.voice.synthesize(text):
                    audio_bytes = audio_chunk.audio_int16_bytes
                    # threadsafe queue put
                    loop.call_soon_threadsafe(queue.put_nowait, audio_bytes)
            except Exception as e:
                logger.error(f"TTS streaming error: {e}")
            finally:
                loop.call_soon_threadsafe(lambda: done_event.set())
                
        # Start worker thread
        loop.run_in_executor(None, lambda: _sync_worker())
        
        while not done_event.is_set() or not queue.empty():
            try:
                # wait for chunks
                chunk = await asyncio.wait_for(queue.get(), timeout=0.1)
                yield chunk
            except asyncio.TimeoutError:
                continue

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    async def main():
        tts = TextToSpeech("hi_IN-priyamvada-medium")
        print("Synthesizing string...")
        async for chunk in tts.synthesize_streaming("नमस्ते! मैं रिया हूँ, आपकी डिजिटल असिस्टेंट।"):
            print(f"Received chunk of size {len(chunk)} bytes")
        print("Done.")
        
    asyncio.run(main())
