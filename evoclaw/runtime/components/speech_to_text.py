#!/usr/bin/env python3
"""
Speech-to-Text Component
Uses faster-whisper for local transcription
"""

import sys
import json
from pathlib import Path

from evoclaw.workspace_resolver import resolve_workspace
from typing import Optional, Dict

WORKSPACE = resolve_workspace(__file__)

# Try to import faster-whisper
try:
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False


class SpeechRecognizer:
    """Speech-to-Text using faster-whisper"""
    
    def __init__(self, model_size: str = "base"):
        self.model = None
        self.model_size = model_size
        self.available = WHISPER_AVAILABLE
        
        if WHISPER_AVAILABLE:
            try:
                # Use smaller model for speed
                self.model = WhisperModel(model_size, device="cpu", compute_type="int8")
                print(f"Loaded whisper model: {model_size}")
            except Exception as e:
                print(f"Failed to load whisper: {e}")
                self.available = False
    
    def transcribe(self, audio_path: str) -> Dict:
        """Transcribe audio file to text"""
        
        if not self.available:
            return {
                "success": False,
                "error": "Whisper not available",
                "text": None
            }
        
        try:
            # Run transcription
            segments, info = self.model.transcribe(audio_path, beam_size=5)
            
            # Collect all segments
            full_text = ""
            for segment in segments:
                full_text += segment.text + " "
            
            return {
                "success": True,
                "text": full_text.strip(),
                "language": info.language if hasattr(info, 'language') else "unknown",
                "language_probability": info.language_probability if hasattr(info, 'language_probability') else 0,
                "duration": info.duration if hasattr(info, 'duration') else 0
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "text": None
            }
    
    def transcribe_ogg(self, ogg_path: str) -> Dict:
        """Transcribe OGG audio file"""
        
        # Convert OGG to WAV if needed
        import subprocess
        import tempfile
        
        wav_path = None
        
        try:
            # Check if ffmpeg is available
            subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
            
            # Convert to temporary WAV
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                wav_path = tmp.name
            
            # Convert
            subprocess.run([
                "ffmpeg", "-i", ogg_path,
                "-acodec", "pcm_s16le",
                "-ac", "1", "-ar", "16000",
                wav_path
            ], capture_output=True)
            
            # Transcribe WAV
            return self.transcribe(wav_path)
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Conversion/transcription failed: {e}",
                "text": None
            }
        
        finally:
            # Cleanup
            if wav_path:
                try:
                    Path(wav_path).unlink()
                except:
                    pass
    
    def is_available(self) -> bool:
        """Check if STT is available"""
        return self.available


# Global instance
_recognizer = None

def get_recognizer(model_size: str = "base") -> SpeechRecognizer:
    global _recognizer
    if _recognizer is None:
        _recognizer = SpeechRecognizer(model_size)
    return _recognizer


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Speech to Text")
    parser.add_argument("audio", help="Audio file path")
    parser.add_argument("--model", default="base", help="Model size")
    
    args = parser.parse_args()
    
    recognizer = get_recognizer(args.model)
    
    if not recognizer.is_available():
        print("Error: Speech recognition not available")
        sys.exit(1)
    
    result = recognizer.transcribe(args.audio)
    
    if result["success"]:
        print(f"Text: {result['text']}")
        print(f"Language: {result.get('language', 'unknown')}")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
