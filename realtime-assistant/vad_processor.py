#!/usr/bin/env python3
"""
Voice Activity Detection and Audio Segmentation for Real-Time Clinical Assistant
Uses Silero VAD to detect patient speech and create segments for transcription
"""
import torch
import numpy as np
import soundfile as sf
from typing import Optional, List, Tuple
import asyncio
import logging
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VADProcessor:
    def __init__(self, 
                 vad_threshold: float = 0.3,
                 sample_rate: int = 16000,
                 min_speech_duration: float = 0.5,
                 max_silence_duration: float = 2.0,
                 max_segment_duration: float = 30.0):
        """
        Initialize VAD processor for clinical conversations
        
        Args:
            vad_threshold: Voice activity threshold (0.3 is good for clinical settings)
            sample_rate: Audio sample rate (16kHz for Parakeet)
            min_speech_duration: Minimum speech segment length in seconds
            max_silence_duration: Maximum silence before processing segment
            max_segment_duration: Maximum segment length to prevent memory issues
        """
        self.vad_threshold = vad_threshold
        self.sample_rate = sample_rate
        self.min_speech_duration = min_speech_duration
        self.max_silence_duration = max_silence_duration
        self.max_segment_duration = max_segment_duration
        
        # Audio buffer management
        self.audio_buffer = []
        self.silence_duration = 0.0
        self.current_segment_duration = 0.0
        self.is_speech_active = False
        
        # VAD model (Silero VAD)
        self.vad_model = None
        self.load_vad_model()
        
        # Statistics
        self.segments_processed = 0
        self.total_speech_time = 0.0
        
    def load_vad_model(self):
        """Load Silero VAD model"""
        try:
            logger.info("Loading Silero VAD model...")
            self.vad_model, _ = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                onnx=False
            )
            logger.info("VAD model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load VAD model: {e}")
            raise
    
    def audio_chunk_to_tensor(self, audio_chunk: bytes) -> torch.Tensor:
        """Convert audio bytes to tensor for VAD processing"""
        try:
            # Convert bytes to numpy array (assuming int16 format from WebRTC)
            audio_np = np.frombuffer(audio_chunk, dtype=np.int16)
            
            # Normalize to float32 [-1, 1]
            audio_float = audio_np.astype(np.float32) / 32767.0
            
            # Convert to tensor
            audio_tensor = torch.from_numpy(audio_float)
            
            return audio_tensor
        except Exception as e:
            logger.error(f"Error converting audio chunk: {e}")
            return torch.empty(0)
    
    async def process_audio_chunk(self, audio_chunk: bytes) -> Optional[bytes]:
        """
        Process incoming audio chunk and return completed speech segment if available
        
        Args:
            audio_chunk: Raw audio bytes (int16 format from WebRTC)
            
        Returns:
            Complete speech segment bytes if ready, None otherwise
        """
        try:
            # Convert to tensor for VAD
            audio_tensor = self.audio_chunk_to_tensor(audio_chunk)
            if audio_tensor.numel() == 0:
                return None
            
            # Run VAD detection
            speech_probability = self.vad_model(audio_tensor, self.sample_rate).item()
            is_speech = speech_probability > self.vad_threshold
            
            # Update timing
            chunk_duration = len(audio_chunk) / 2 / self.sample_rate  # bytes -> samples -> seconds
            self.current_segment_duration += chunk_duration
            
            if is_speech:
                # Speech detected - add to buffer
                self.audio_buffer.append(audio_chunk)
                self.silence_duration = 0.0
                self.is_speech_active = True
                
                logger.debug(f"Speech detected (prob: {speech_probability:.2f})")
                
            else:
                # Silence detected
                self.silence_duration += chunk_duration
                
                # Add silence to buffer if we're in an active speech segment
                if self.is_speech_active:
                    self.audio_buffer.append(audio_chunk)
                
                logger.debug(f"Silence detected, duration: {self.silence_duration:.2f}s")
            
            # Check if we should finalize the current segment
            should_finalize = (
                self.is_speech_active and (
                    self.silence_duration >= self.max_silence_duration or
                    self.current_segment_duration >= self.max_segment_duration
                )
            )
            
            if should_finalize:
                return await self.finalize_segment()
            
            return None
            
        except Exception as e:
            logger.error(f"Error processing audio chunk: {e}")
            return None
    
    async def finalize_segment(self) -> Optional[bytes]:
        """Finalize current speech segment and return audio data"""
        try:
            if not self.audio_buffer:
                return None
            
            # Check minimum duration
            if self.current_segment_duration < self.min_speech_duration:
                logger.debug(f"Segment too short ({self.current_segment_duration:.2f}s), discarding")
                self.reset_segment()
                return None
            
            # Combine audio buffer
            complete_segment = b''.join(self.audio_buffer)
            
            # Update statistics
            self.segments_processed += 1
            self.total_speech_time += self.current_segment_duration
            
            logger.info(f"Finalized speech segment #{self.segments_processed} "
                       f"({self.current_segment_duration:.2f}s, {len(complete_segment)} bytes)")
            
            # Reset for next segment
            self.reset_segment()
            
            return complete_segment
            
        except Exception as e:
            logger.error(f"Error finalizing segment: {e}")
            self.reset_segment()
            return None
    
    def reset_segment(self):
        """Reset segment state for next speech detection"""
        self.audio_buffer = []
        self.silence_duration = 0.0
        self.current_segment_duration = 0.0
        self.is_speech_active = False
    
    def get_statistics(self) -> dict:
        """Get VAD processing statistics"""
        return {
            "segments_processed": self.segments_processed,
            "total_speech_time": self.total_speech_time,
            "average_segment_duration": (
                self.total_speech_time / self.segments_processed 
                if self.segments_processed > 0 else 0
            ),
            "vad_threshold": self.vad_threshold,
            "is_active": self.is_speech_active
        }

# Test function for development
async def test_vad_processor():
    """Test VAD processor with sample audio"""
    processor = VADProcessor(vad_threshold=0.3)
    
    # Simulate audio chunks (would come from WebSocket in real use)
    sample_rate = 16000
    chunk_size = 1024  # samples
    
    # Generate test audio (silence + tone + silence)
    test_duration = 5.0  # seconds
    test_samples = int(test_duration * sample_rate)
    
    # Create test signal: 1 second silence, 3 seconds tone, 1 second silence
    test_audio = np.zeros(test_samples, dtype=np.float32)
    tone_start = sample_rate  # 1 second
    tone_end = 4 * sample_rate  # 4 seconds
    test_audio[tone_start:tone_end] = 0.1 * np.sin(2 * np.pi * 440 * np.arange(tone_end - tone_start) / sample_rate)
    
    # Convert to int16 bytes
    test_audio_int16 = (test_audio * 32767).astype(np.int16)
    test_bytes = test_audio_int16.tobytes()
    
    # Process in chunks
    segments = []
    for i in range(0, len(test_bytes), chunk_size * 2):  # *2 for int16 bytes
        chunk = test_bytes[i:i + chunk_size * 2]
        segment = await processor.process_audio_chunk(chunk)
        if segment:
            segments.append(segment)
    
    print(f"Processed {len(segments)} speech segments")
    print(f"Statistics: {processor.get_statistics()}")

if __name__ == "__main__":
    asyncio.run(test_vad_processor())