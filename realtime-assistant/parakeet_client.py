#!/usr/bin/env python3
"""
Parakeet WebSocket Client for Real-Time Clinical Assistant
Connects to existing Parakeet FastAPI WebSocket for real-time transcription
"""
import asyncio
import websockets
import json
import logging
import os
from typing import Optional, Callable, Any
import numpy as np

logger = logging.getLogger(__name__)

# Default Parakeet URL from environment
DEFAULT_PARAKEET_URL = os.environ.get("PARAKEET_WS_URL", "ws://parakeet-asr:8000/ws")

class ParakeetWebSocketClient:
    """Client for connecting to Parakeet's WebSocket transcription service"""
    
    def __init__(self, parakeet_url: str = None):
        self.parakeet_url = parakeet_url or DEFAULT_PARAKEET_URL
        self.websocket = None
        self.is_connected = False
        self.transcription_callback = None
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 2  # seconds
        
    def set_transcription_callback(self, callback: Callable[[str, float], None]):
        """Set callback function to handle transcription results"""
        self.transcription_callback = callback
    
    async def connect(self):
        """Connect to Parakeet WebSocket"""
        try:
            logger.info(f"Connecting to Parakeet WebSocket at {self.parakeet_url}")
            self.websocket = await websockets.connect(self.parakeet_url)
            self.is_connected = True
            logger.info("Connected to Parakeet WebSocket successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Parakeet WebSocket: {e}")
            self.is_connected = False
            raise
    
    async def disconnect(self):
        """Disconnect from Parakeet WebSocket"""
        if self.websocket:
            await self.websocket.close()
            self.is_connected = False
            logger.info("Disconnected from Parakeet WebSocket")
    
    async def send_audio_chunk(self, audio_data: bytes):
        """
        Send audio chunk to Parakeet for transcription
        
        Args:
            audio_data: Raw audio bytes (16kHz mono PCM, int16)
        """
        if not self.is_connected or not self.websocket:
            logger.warning("Not connected to Parakeet WebSocket")
            return
        
        try:
            await self.websocket.send(audio_data)
            logger.debug(f"Sent audio chunk of {len(audio_data)} bytes")
        except Exception as e:
            logger.error(f"Error sending audio chunk: {e}")
            self.is_connected = False
    
    async def listen_for_transcriptions(self):
        """Listen for transcription results from Parakeet with auto-reconnect"""
        while True:
            if not self.is_connected or not self.websocket:
                if not await self._try_reconnect():
                    logger.error("Failed to reconnect to Parakeet, stopping listener")
                    return
            
            try:
                async for message in self.websocket:
                    self.reconnect_attempts = 0  # Reset on successful message
                    await self.handle_transcription_message(message)
            except websockets.exceptions.ConnectionClosed:
                logger.warning("Parakeet WebSocket connection closed, attempting reconnect...")
                self.is_connected = False
            except Exception as e:
                logger.error(f"Error listening for transcriptions: {e}")
                self.is_connected = False
    
    async def _try_reconnect(self) -> bool:
        """Attempt to reconnect to Parakeet WebSocket"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"Max reconnect attempts ({self.max_reconnect_attempts}) reached")
            return False
        
        self.reconnect_attempts += 1
        delay = self.reconnect_delay * self.reconnect_attempts
        logger.info(f"Reconnect attempt {self.reconnect_attempts}/{self.max_reconnect_attempts} in {delay}s...")
        
        await asyncio.sleep(delay)
        
        try:
            await self.connect()
            logger.info("Reconnected to Parakeet WebSocket successfully")
            return True
        except Exception as e:
            logger.error(f"Reconnect attempt failed: {e}")
            return False
    
    async def handle_transcription_message(self, message: str):
        """Handle incoming transcription message from Parakeet"""
        try:
            # Parse JSON message
            data = json.loads(message)
            
            # Handle different message types
            if "status" in data:
                # Status message (e.g., {"status": "queued"})
                logger.debug(f"Parakeet status: {data['status']}")
                
            elif "text" in data:
                # Transcription result
                text = data["text"].strip()
                confidence = data.get("confidence", 0.0)
                
                if text and self.transcription_callback:
                    logger.info(f"Received transcription: {text}")
                    await self.transcription_callback(text, confidence)
                    
        except json.JSONDecodeError:
            logger.warning(f"Received non-JSON message: {message}")
        except Exception as e:
            logger.error(f"Error handling transcription message: {e}")

class AudioForwarder:
    """Forwards audio from telesalud to Parakeet and handles responses"""
    
    def __init__(self, consultation_id: str, transcription_processor):
        self.consultation_id = consultation_id
        self.transcription_processor = transcription_processor
        self.parakeet_client = ParakeetWebSocketClient()
        self.is_active = False
        
        # Set up transcription callback
        self.parakeet_client.set_transcription_callback(self.on_transcription)
    
    async def start(self):
        """Start the audio forwarding service"""
        try:
            await self.parakeet_client.connect()
            self.is_active = True
            
            # Start listening for transcriptions in background
            asyncio.create_task(self.parakeet_client.listen_for_transcriptions())
            
            logger.info(f"Audio forwarder started for consultation {self.consultation_id}")
            
        except Exception as e:
            logger.error(f"Failed to start audio forwarder: {e}")
            raise
    
    async def stop(self):
        """Stop the audio forwarding service"""
        self.is_active = False
        await self.parakeet_client.disconnect()
        logger.info(f"Audio forwarder stopped for consultation {self.consultation_id}")
    
    async def forward_audio_chunk(self, audio_data: bytes):
        """Forward audio chunk from telesalud to Parakeet"""
        if self.is_active:
            await self.parakeet_client.send_audio_chunk(audio_data)
    
    async def on_transcription(self, text: str, confidence: float):
        """Handle transcription result from Parakeet"""
        try:
            # Forward transcription to the clinical assistant processor
            await self.transcription_processor.process_transcription(
                self.consultation_id, text, confidence
            )
        except Exception as e:
            logger.error(f"Error processing transcription: {e}")

class TranscriptionProcessor:
    """Processes transcriptions and generates clinical suggestions"""
    
    def __init__(self, clinical_engine):
        self.clinical_engine = clinical_engine
        self.session_manager = None  # Will be set from main app
    
    async def process_transcription(self, consultation_id: str, text: str, confidence: float):
        """Process a transcription and generate clinical suggestions"""
        try:
            # Get or create session
            session = self.session_manager.get_session(consultation_id)
            if not session:
                logger.warning(f"No session found for consultation {consultation_id}")
                return
            
            # Queue the transcription for clinical analysis
            await self.clinical_engine.queue_patient_statement(session, text)
            
            logger.info(f"Processed transcription for {consultation_id}: {text[:50]}...")
            
        except Exception as e:
            logger.error(f"Error processing transcription: {e}")

# Factory function to create audio forwarder
def create_audio_forwarder(consultation_id: str, clinical_engine) -> AudioForwarder:
    """Create an audio forwarder for a consultation"""
    transcription_processor = TranscriptionProcessor(clinical_engine)
    return AudioForwarder(consultation_id, transcription_processor)