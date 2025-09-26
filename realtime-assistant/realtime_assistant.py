#!/usr/bin/env python3
"""
Real-Time Clinical Assistant Main Server
Coordinates audio streaming, transcription, and clinical suggestions
"""
import asyncio
import websockets
import json
import logging
import os
from typing import Dict, Any, Optional
from datetime import datetime

# Import our modules
from conversation_state import session_manager, ConsultationType, periodic_cleanup
from telesalud_integration import assistant_engine
from parakeet_client import create_audio_forwarder

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RealtimeAssistantServer:
    """Main server for real-time clinical assistant"""
    
    def __init__(self):
        self.port = int(os.environ.get("REALTIME_PORT", 9091))
        self.host = os.environ.get("REALTIME_HOST", "0.0.0.0")
        self.active_connections = {}  # consultation_id -> websocket
        self.audio_forwarders = {}    # consultation_id -> AudioForwarder
        
        # Set up suggestion callback
        assistant_engine.add_suggestion_callback(self.send_suggestion_to_telesalud)
    
    async def start_server(self):
        """Start the WebSocket server"""
        logger.info(f"Starting Real-Time Clinical Assistant Server on {self.host}:{self.port}")
        
        # Start background tasks
        asyncio.create_task(assistant_engine.start_processing_queue())
        asyncio.create_task(periodic_cleanup())
        
        # Start WebSocket server
        async with websockets.serve(self.handle_connection, self.host, self.port):
            logger.info("Real-Time Clinical Assistant Server is running")
            await asyncio.Future()  # Run forever
    
    async def handle_connection(self, websocket, path):
        """Handle new WebSocket connection from telesalud"""
        try:
            logger.info(f"New WebSocket connection from {websocket.remote_address}")
            
            async for message in websocket:
                await self.handle_message(websocket, message)
                
        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket connection closed")
        except Exception as e:
            logger.error(f"Error handling WebSocket connection: {e}")
        finally:
            await self.cleanup_connection(websocket)
    
    async def handle_message(self, websocket, message):
        """Handle incoming message from telesalud"""
        try:
            # Parse message
            if isinstance(message, bytes):
                # Audio data - forward to Parakeet
                await self.handle_audio_data(websocket, message)
            else:
                # JSON control message
                data = json.loads(message)
                await self.handle_control_message(websocket, data)
                
        except json.JSONDecodeError:
            logger.warning("Received invalid JSON message")
            await self.send_error(websocket, "Invalid JSON format")
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            await self.send_error(websocket, f"Message handling error: {str(e)}")
    
    async def handle_control_message(self, websocket, data: Dict[str, Any]):
        """Handle JSON control messages from telesalud"""
        message_type = data.get("type")
        
        if message_type == "start_session":
            await self.start_consultation_session(websocket, data)
            
        elif message_type == "end_session":
            await self.end_consultation_session(websocket, data)
            
        elif message_type == "provider_question":
            await self.handle_provider_question(websocket, data)
            
        elif message_type == "ping":
            await self.send_message(websocket, {"type": "pong", "timestamp": datetime.now().isoformat()})
            
        else:
            logger.warning(f"Unknown message type: {message_type}")
            await self.send_error(websocket, f"Unknown message type: {message_type}")
    
    async def start_consultation_session(self, websocket, data: Dict[str, Any]):
        """Start a new consultation session"""
        try:
            consultation_id = data.get("consultation_id")
            consultation_type = data.get("consultation_type", "general")
            
            if not consultation_id:
                await self.send_error(websocket, "Missing consultation_id")
                return
            
            # Create conversation session
            session = await session_manager.create_session(consultation_id, consultation_type)
            
            # Create audio forwarder for Parakeet integration
            audio_forwarder = create_audio_forwarder(consultation_id, assistant_engine)
            
            # Set session manager reference
            audio_forwarder.transcription_processor.session_manager = session_manager
            
            # Start audio forwarder
            await audio_forwarder.start()
            
            # Store connections
            self.active_connections[consultation_id] = websocket
            self.audio_forwarders[consultation_id] = audio_forwarder
            
            # Send confirmation
            await self.send_message(websocket, {
                "type": "session_started",
                "consultation_id": consultation_id,
                "consultation_type": consultation_type,
                "timestamp": datetime.now().isoformat()
            })
            
            logger.info(f"Started consultation session: {consultation_id} (type: {consultation_type})")
            
        except Exception as e:
            logger.error(f"Error starting consultation session: {e}")
            await self.send_error(websocket, f"Failed to start session: {str(e)}")
    
    async def end_consultation_session(self, websocket, data: Dict[str, Any]):
        """End a consultation session"""
        try:
            consultation_id = data.get("consultation_id")
            
            if consultation_id in self.active_connections:
                # Stop audio forwarder
                if consultation_id in self.audio_forwarders:
                    await self.audio_forwarders[consultation_id].stop()
                    del self.audio_forwarders[consultation_id]
                
                # Get session summary
                session = session_manager.get_session(consultation_id)
                summary = session.get_session_summary() if session else {}
                
                # Clean up
                del self.active_connections[consultation_id]
                
                # Send confirmation with summary
                await self.send_message(websocket, {
                    "type": "session_ended",
                    "consultation_id": consultation_id,
                    "session_summary": summary,
                    "timestamp": datetime.now().isoformat()
                })
                
                logger.info(f"Ended consultation session: {consultation_id}")
            
        except Exception as e:
            logger.error(f"Error ending consultation session: {e}")
            await self.send_error(websocket, f"Failed to end session: {str(e)}")
    
    async def handle_provider_question(self, websocket, data: Dict[str, Any]):
        """Handle provider question/statement"""
        try:
            consultation_id = data.get("consultation_id")
            question_text = data.get("text", "")
            
            session = session_manager.get_session(consultation_id)
            if session:
                await session.add_provider_statement(question_text)
                logger.info(f"Added provider question to session {consultation_id}")
            
        except Exception as e:
            logger.error(f"Error handling provider question: {e}")
    
    async def handle_audio_data(self, websocket, audio_data: bytes):
        """Handle incoming audio data"""
        try:
            # Find consultation ID for this websocket
            consultation_id = None
            for cid, ws in self.active_connections.items():
                if ws == websocket:
                    consultation_id = cid
                    break
            
            if not consultation_id:
                logger.warning("Received audio data from unregistered connection")
                return
            
            # Forward to Parakeet via audio forwarder
            if consultation_id in self.audio_forwarders:
                await self.audio_forwarders[consultation_id].forward_audio_chunk(audio_data)
            
        except Exception as e:
            logger.error(f"Error handling audio data: {e}")
    
    async def send_suggestion_to_telesalud(self, consultation_id: str, suggestions: Dict[str, Any]):
        """Send clinical suggestions back to telesalud"""
        try:
            if consultation_id in self.active_connections:
                websocket = self.active_connections[consultation_id]
                
                message = {
                    "type": "clinical_suggestion",
                    "consultation_id": consultation_id,
                    "suggestions": suggestions,
                    "timestamp": datetime.now().isoformat()
                }
                
                await self.send_message(websocket, message)
                logger.info(f"Sent clinical suggestion to consultation {consultation_id}")
            
        except Exception as e:
            logger.error(f"Error sending suggestion: {e}")
    
    async def send_message(self, websocket, message: Dict[str, Any]):
        """Send JSON message to websocket"""
        try:
            await websocket.send(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending message: {e}")
    
    async def send_error(self, websocket, error_message: str):
        """Send error message to websocket"""
        await self.send_message(websocket, {
            "type": "error",
            "message": error_message,
            "timestamp": datetime.now().isoformat()
        })
    
    async def cleanup_connection(self, websocket):
        """Clean up connection when websocket closes"""
        try:
            # Find and remove connection
            consultation_id = None
            for cid, ws in self.active_connections.items():
                if ws == websocket:
                    consultation_id = cid
                    break
            
            if consultation_id:
                # Stop audio forwarder
                if consultation_id in self.audio_forwarders:
                    await self.audio_forwarders[consultation_id].stop()
                    del self.audio_forwarders[consultation_id]
                
                # Remove connection
                del self.active_connections[consultation_id]
                
                logger.info(f"Cleaned up connection for consultation {consultation_id}")
            
        except Exception as e:
            logger.error(f"Error cleaning up connection: {e}")
    
    async def get_server_status(self):
        """Get server status for health checks"""
        return {
            "status": "running",
            "active_sessions": len(self.active_connections),
            "audio_forwarders": len(self.audio_forwarders),
            "timestamp": datetime.now().isoformat(),
            "all_sessions": session_manager.get_all_active_sessions()
        }

async def main():
    """Main entry point"""
    try:
        server = RealtimeAssistantServer()
        await server.start_server()
    except KeyboardInterrupt:
        logger.info("Shutting down Real-Time Clinical Assistant Server")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())