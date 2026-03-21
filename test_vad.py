import torch
import numpy as np

try:
    model, utils = torch.hub.load(
        repo_or_dir='snakers4/silero-vad',
        model='silero_vad',
        onnx=False,
        trust_repo=True
    )
    (get_speech_timestamps, save_audio, read_audio, VADIterator, collect_chunks) = utils
    
    # Create fake audio 16kHz (512 samples)
    audio = torch.rand(512)
    
    # test inference
    speech_prob = model(audio, 16000).item()
    print("Inference successful. Speech prob:", speech_prob)
except Exception as e:
    print("Error:", repr(e))
