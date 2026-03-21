import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.models import Lead
from backend.call_controller import CallController
from backend.conversation_loop import run_conversation

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MockCallController(CallController):
    def __init__(self):
        super().__init__()
        self.active = True

    async def connect(self):
        pass

    async def start_call(self, phone: str) -> bool:
        self._connected_event.set()
        return True

    async def end_call(self):
        logger.info("MockCallController: end_call() called.")
        self.active = False
        
    async def send_dtmf(self, digits: str):
        pass

    async def send_audio(self, pcm_chunk: bytes):
        # We don't need to log every chunk to avoid spam
        pass

    async def receive_loop(self):
        pass

    async def disconnect(self):
        pass
        
    def inject_audio(self, pcm_chunk: bytes):
        for cb in self._audio_in_callbacks:
            cb(pcm_chunk)

async def main():
    logger.info("Starting mock conversation loop.")
    lead = Lead(
        row_index=1,
        id="test_lead_1",
        company_name="Test Corp",
        owner_name="Amit",
        phone="1234567890",
        business_type="Retail",
        city="Mumbai"
    )
    controller = MockCallController()
    await controller.start_call(lead.phone)
    
    from backend.recording_manager import RecordingManager
    recorder = RecordingManager()
    
    # Run the loop as a background task
    loop_task = asyncio.create_task(run_conversation(lead, controller, recorder))
    
    # Wait for the greeting to be synthesized and sent
    logger.info("Waiting for agent to play greeting...")
    await asyncio.sleep(8)
    
    # Inject silence
    logger.info("Injecting 1s of silence from customer...")
    silence = b"\0" * (16000 * 2)
    controller.inject_audio(silence)
    
    await asyncio.sleep(2)
    
    logger.info("Canceling conversation loop...")
    loop_task.cancel()
    try:
        await loop_task
    except asyncio.CancelledError:
        logger.info("Loop cancelled.")
        
if __name__ == "__main__":
    asyncio.run(main())
