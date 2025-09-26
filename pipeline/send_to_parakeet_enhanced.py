#!/usr/bin/env python3
"""
Enhanced Parakeet client that can handle both MKA and WAV files
Attempts to send MKA directly if Parakeet supports it, otherwise uses WAV
"""
import sys
import json
import websocket
import wave
import os
import subprocess
from threading import Thread
import tempfile

PARAKEET_WS_URL = os.environ.get("PARAKEET_WS_URL", "ws://parakeet-asr:8000/ws/transcribe")
PARAKEET_HTTP_URL = os.environ.get("PARAKEET_HTTP_URL", "http://parakeet-asr:8000/transcribe")

def check_file_format(file_path):
    """Determine if file is MKA or WAV"""
    extension = os.path.splitext(file_path)[1].lower()
    return extension.replace('.', '')

def try_send_mka_http(mka_file):
    """
    Try to send MKA file directly to Parakeet via HTTP POST
    This would be the ideal path if Parakeet supports it
    """
    try:
        import requests

        print(f"[🚀] Attempting to send MKA file directly to Parakeet...")

        with open(mka_file, 'rb') as f:
            files = {'audio': (os.path.basename(mka_file), f, 'audio/x-matroska')}
            response = requests.post(
                PARAKEET_HTTP_URL,
                files=files,
                timeout=300  # 5 minute timeout for large files
            )

        if response.status_code == 200:
            print(f"[✅] Parakeet successfully processed MKA file")
            return response.json()
        else:
            print(f"[⚠️] Parakeet returned status {response.status_code}")
            return None

    except requests.exceptions.ConnectionError:
        print(f"[⚠️] Parakeet HTTP endpoint not available")
        return None
    except Exception as e:
        print(f"[⚠️] Failed to send MKA via HTTP: {e}")
        return None

def stream_mka_via_websocket(mka_file, output_file):
    """
    Stream MKA file to Parakeet by converting on-the-fly with ffmpeg
    This avoids creating intermediate WAV files
    """
    print(f"[🔄] Streaming MKA to Parakeet via ffmpeg pipe...")

    transcripts = []

    def on_message(ws, message):
        try:
            data = json.loads(message)
            if 'text' in data:
                transcripts.append(data)
                print(f"[📝] Partial: {data.get('text', '')}")
        except json.JSONDecodeError:
            print(f"[⚠️] Failed to parse message: {message}")

    def on_error(ws, error):
        print(f"[❌] WebSocket error: {error}")

    def on_close(ws, close_status_code, close_msg):
        print(f"[🔌] WebSocket closed")
        with open(output_file, 'w') as f:
            json.dump({
                'file': os.path.basename(mka_file),
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

            # Use ffmpeg to convert MKA to PCM on the fly
            ffmpeg_cmd = [
                'ffmpeg',
                '-i', mka_file,
                '-f', 's16le',  # Raw PCM
                '-ar', '16000',  # 16kHz
                '-ac', '1',      # Mono
                '-',             # Output to stdout
                '-loglevel', 'error'
            ]

            process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE)

            # Stream the converted audio
            while True:
                data = process.stdout.read(1024)
                if not data:
                    break
                ws.send(data, websocket.ABNF.OPCODE_BINARY)

            process.wait()

            # Signal end of audio
            ws.send(json.dumps({"action": "end_of_audio"}))
            ws.close()

        thread = Thread(target=run)
        thread.start()

    # Connect and stream
    ws = websocket.WebSocketApp(PARAKEET_WS_URL,
                                on_open=on_open,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)

    ws.run_forever()
    return True

def send_wav_via_websocket(wav_file, output_file):
    """Original WAV sending method via WebSocket"""
    print(f"[🎤] Sending WAV file to Parakeet...")

    transcripts = []

    def on_message(ws, message):
        try:
            data = json.loads(message)
            if 'text' in data:
                transcripts.append(data)
                print(f"[📝] Partial: {data.get('text', '')}")
        except json.JSONDecodeError:
            print(f"[⚠️] Failed to parse message: {message}")

    def on_error(ws, error):
        print(f"[❌] WebSocket error: {error}")

    def on_close(ws, close_status_code, close_msg):
        print(f"[🔌] WebSocket closed")
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
    return True

def send_to_parakeet(audio_file):
    """
    Main function that handles both MKA and WAV files
    Tries optimal path first, falls back as needed
    """

    print(f"[🎵] Processing {audio_file}")

    file_format = check_file_format(audio_file)
    output_file = audio_file.replace(f'.{file_format}', '_transcript.json')

    if file_format == 'mka':
        # Try 1: Send MKA directly via HTTP (if Parakeet supports it)
        result = try_send_mka_http(audio_file)
        if result:
            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2)
            return True

        # Try 2: Stream MKA via WebSocket with on-the-fly conversion
        print(f"[📡] HTTP not available, trying WebSocket streaming...")
        return stream_mka_via_websocket(audio_file, output_file)

    elif file_format == 'wav':
        # WAV file - use original WebSocket method
        return send_wav_via_websocket(audio_file, output_file)

    else:
        print(f"[❌] Unsupported file format: {file_format}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: send_to_parakeet_enhanced.py <audio_file>")
        print("Supports: .mka, .wav")
        sys.exit(1)

    success = send_to_parakeet(sys.argv[1])
    sys.exit(0 if success else 1)