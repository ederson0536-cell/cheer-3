#!/usr/bin/env python3
"""
Voice Message Processor
Integrates speech-to-text into message handling
"""

import subprocess
import os
from pathlib import Path

from evoclaw.workspace_resolver import resolve_workspace

WORKSPACE = resolve_workspace(__file__)
MEDIA_DIR = WORKSPACE / "media" / "inbound"

# Import speech recognition
import sys
sys.path.insert(0, str(WORKSPACE / "evoclaw" / "runtime"))
from components.speech_to_text import get_recognizer


class VoiceProcessor:
    """Process voice messages"""
    
    def __init__(self):
        self.recognizer = get_recognizer()
        self.media_dir = MEDIA_DIR
    
    def has_voice(self, message_info: dict) -> bool:
        """Check if message has voice/audio"""
        
        # Check for voice file indicators
        # This would be passed from the message metadata
        return message_info.get("has_voice", False)
    
    def process_voice_file(self, file_path: str) -> str:
        """Process a voice file and return transcribed text"""
        
        if not os.path.exists(file_path):
            return None
        
        # Convert to WAV
        wav_path = "/tmp/voice_processed.wav"
        
        result = subprocess.run([
            "ffmpeg", "-i", file_path,
            "-acodec", "pcm_s16le",
            "-ac", "1", "-ar", "16000",
            "-y", wav_path
        ], capture_output=True)
        
        if result.returncode != 0:
            print(f"Voice conversion failed: {result.stderr.decode()[:100]}")
            return None
        
        # Transcribe
        result = self.recognizer.transcribe(wav_path)
        
        # Cleanup
        try:
            os.remove(wav_path)
        except:
            pass
        
        if result.get("success"):
            return result.get("text")
        
        return None
    
    def get_latest_voice(self) -> str:
        """Get the latest voice file from inbound"""
        
        if not self.media_dir.exists():
            return None
        
        voice_files = list(self.media_dir.glob("*.ogg"))
        
        if not voice_files:
            return None
        
        # Get most recent
        latest = max(voice_files, key=os.path.getmtime)
        return str(latest)
    
    def process_latest(self) -> str:
        """Process the latest voice file"""
        
        latest = self.get_latest_voice()
        
        if not latest:
            return None
        
        return self.process_voice_file(latest)


def process_inbound_voice() -> str:
    """Process any inbound voice messages"""
    
    processor = VoiceProcessor()
    
    # Try to process latest voice
    text = processor.process_latest()
    
    if text:
        print(f"Voice transcribed: {text}")
        return text
    
    return None


# Test
if __name__ == "__main__":
    result = process_inbound_voice()
    
    if result:
        print(f"Transcribed: {result}")
    else:
        print("No voice to process")
