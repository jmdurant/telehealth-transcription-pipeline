#!/usr/bin/env python3
import sys
import json
import websocket
import wave
import os
from threading import Thread

PARAKEET_WS_URL = os.environ.get("PARAKEET_WS_URL", "ws://parakeet-asr:8000/ws/transcribe")

def send_to_parakeet(wav_file):
    """Send WAV file to Parakeet ASR via WebSocket and save transcription"""
    
    print(f"[🎤 ASR] Transcribing {wav_file}")
    
    # Output file for transcription
    output_file = wav_file.replace('.wav', '_transcript.json')
    transcripts = []
    
    def on_message(ws, message):
        """Handle incoming transcription messages"""
        try:
            data = json.loads(message)
            if 'text' in data:
                transcripts.append(data)
                print(f"[📝] Partial: {data.get('text', '')}")
        except json.JSONDecodeError:
            print(f"[⚠️] Failed to parse message: {message}")
    
    def on_error(ws, error):
        print(f"[❌ ERROR] WebSocket error: {error}")
    
    def on_close(ws, close_status_code, close_msg):
        print(f"[🔌] WebSocket closed")
        # Save all transcripts
        with open(output_file, 'w') as f:
            json.dump({
                'file': os.path.basename(wav_file),
                'transcripts': transcripts
            }, f, indent=2)
        print(f"[✅] Saved transcript to {output_file}")
    
    def on_open(ws):
        def run():
            # Send audio config
            config = {
                "config": {
                    "sample_rate": 16000,
                    "language": "en",
                    "encoding": "LINEAR16"
                }
            }
            ws.send(json.dumps(config))
            
            # Send audio data
            with wave.open(wav_file, 'rb') as wav:
                while True:
                    data = wav.readframes(1024)
                    if not data:
                        break
                    ws.send(data, websocket.ABNF.OPCODE_BINARY)
            
            # Signal end of audio
            ws.send(json.dumps({"action": "end_of_audio"}))
            ws.close()
        
        thread = Thread(target=run)
        thread.start()
    
    # Connect to WebSocket
    ws = websocket.WebSocketApp(PARAKEET_WS_URL,
                                on_open=on_open,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    
    ws.run_forever()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: send_to_parakeet.py <wav_file>")
        sys.exit(1)
    
    send_to_parakeet(sys.argv[1])