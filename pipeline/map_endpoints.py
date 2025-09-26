#!/usr/bin/env python3
import sys
import json
import os
import requests

PROSODY_API_URL = os.environ.get("PROSODY_API_URL", "http://prosody:5280/event_sync")

def map_endpoints_from_prosody(event_log_file):
    """Map Jitsi endpoints to speaker names using Prosody event logs"""
    
    print(f"[🗺️ MAP] Mapping speakers from {event_log_file}")
    
    speaker_mapping = {}
    
    # Try to load event log if it exists
    if os.path.exists(event_log_file):
        try:
            with open(event_log_file, 'r') as f:
                events = json.load(f)
            
            # Parse events to extract participant info
            participants = {}
            
            for event in events:
                if event.get('type') == 'participant_joined':
                    endpoint_id = event.get('endpoint_id')
                    display_name = event.get('display_name', f'Speaker {len(participants) + 1}')
                    participants[endpoint_id] = display_name
                    
            # Map audio tracks to participants
            track_counter = 1
            for event in events:
                if event.get('type') == 'track_added' and event.get('media_type') == 'audio':
                    endpoint_id = event.get('endpoint_id')
                    if endpoint_id in participants:
                        speaker_key = f"speaker{track_counter}"
                        speaker_mapping[speaker_key] = participants[endpoint_id]
                        track_counter += 1
                        
        except Exception as e:
            print(f"[⚠️] Error parsing event log: {e}")
    
    # Try to fetch from Prosody API if available
    else:
        try:
            # Extract room name from log file name
            room_name = os.path.basename(event_log_file).replace('.json', '')
            
            response = requests.get(f"{PROSODY_API_URL}/room/{room_name}/participants")
            if response.status_code == 200:
                participants = response.json()
                
                for idx, participant in enumerate(participants):
                    speaker_key = f"speaker{idx + 1}"
                    display_name = participant.get('display_name', f'Speaker {idx + 1}')
                    speaker_mapping[speaker_key] = display_name
                    
        except Exception as e:
            print(f"[⚠️] Error fetching from Prosody API: {e}")
    
    # If no mapping found, create default mapping
    if not speaker_mapping:
        print("[⚠️] No speaker mapping found, using defaults")
        # Assume standard multitrack output naming
        for i in range(1, 10):  # Support up to 10 speakers
            speaker_mapping[f"speaker{i}"] = f"Speaker {i}"
    
    # Save speaker mapping
    recording_dir = os.path.dirname(event_log_file)
    if not recording_dir:
        recording_dir = "."
        
    output_file = os.path.join(recording_dir, "speaker_mapping.json")
    
    with open(output_file, 'w') as f:
        json.dump(speaker_mapping, f, indent=2)
    
    print(f"[✅] Saved speaker mapping to {output_file}")
    print(f"[👥] Mapping: {speaker_mapping}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: map_endpoints.py <event_log_file>")
        sys.exit(1)
    
    map_endpoints_from_prosody(sys.argv[1])