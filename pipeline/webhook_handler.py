#!/usr/bin/env python3
"""
Webhook handler for receiving telesalud consultation notifications
Listens for videoconsultation events and stores metadata for pipeline processing
"""
import json
import os
import subprocess
from datetime import datetime
from flask import Flask, request, jsonify
import threading
import time

app = Flask(__name__)

# Directory to store consultation metadata
METADATA_DIR = os.environ.get("METADATA_DIR", "/shared/consultations")
WEBHOOK_TOKEN = os.environ.get("WEBHOOK_TOKEN", "")

def ensure_metadata_dir():
    """Ensure metadata directory exists"""
    os.makedirs(METADATA_DIR, exist_ok=True)

def trigger_pipeline_async(consultation_id):
    """Trigger the pipeline processing asynchronously for webhook mode"""
    def run_pipeline():
        try:
            # Wait a moment to ensure recording is fully written
            time.sleep(5)

            # Check if already being processed (lock exists)
            metadata_dir = os.environ.get("METADATA_DIR", "/shared/consultations")
            lock_file = os.path.join(metadata_dir, f"{consultation_id}.lock")

            if os.path.exists(lock_file):
                print(f"[🔒] Consultation {consultation_id} already being processed")
                print(f"[⏭️] Webhook trigger skipped - Jitsi likely already processing")
                return

            # Determine recording directory (this assumes standard Jitsi naming)
            recording_dir = f"/recordings/{consultation_id}"

            # Check if recording directory exists
            if not os.path.exists(recording_dir):
                print(f"[⚠️] Recording directory not found yet: {recording_dir}")
                # Could implement retry logic here
                return

            print(f"[🚀] Triggering pipeline for consultation {consultation_id}")

            # Call the wrapper script with webhook trigger source
            result = subprocess.run(
                ["/pipeline/finalize_wrapper.sh", recording_dir, "webhook", consultation_id],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                print(f"[✅] Pipeline completed successfully for {consultation_id}")
            else:
                print(f"[❌] Pipeline failed for {consultation_id}: {result.stderr}")

        except Exception as e:
            print(f"[❌] Error triggering pipeline: {str(e)}")

    # Run in background thread
    thread = threading.Thread(target=run_pipeline)
    thread.daemon = True
    thread.start()
    print(f"[🔄] Pipeline triggered in background for {consultation_id}")

def save_event_notification(vc_data, topic):
    """Save minimal event notification (no patient data for security)"""
    ensure_metadata_dir()
    
    consultation_id = vc_data.get('secret')
    if not consultation_id:
        return False
    
    # Only save minimal event data - no patient information
    event_data = {
        'consultation_id': consultation_id,
        'status': vc_data.get('status'),
        'topic': topic,
        'webhook_received': datetime.now().isoformat(),
        'patient_data_retrieved': False,
        'recording_processed': False
    }
    
    # Save to file
    filename = f"{consultation_id}_event.json"
    filepath = os.path.join(METADATA_DIR, filename)
    
    with open(filepath, 'w') as f:
        json.dump(event_data, f, indent=2)
    
    print(f"[📋 WEBHOOK] Saved event notification for consultation {consultation_id}")
    return True

@app.route('/webhook/telesalud', methods=['POST'])
def handle_telesalud_webhook():
    """Handle incoming telesalud webhooks"""
    
    # Verify webhook token if configured
    if WEBHOOK_TOKEN:
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer ') or auth_header[7:] != WEBHOOK_TOKEN:
            return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        vc_data = data.get('vc', {})
        topic = data.get('topic', '')
        
        print(f"[🔗 WEBHOOK] Received {topic} for consultation {vc_data.get('secret')}")
        
        # Save event notification (minimal data only)
        if save_event_notification(vc_data, topic):
            
            # Trigger pipeline processing if consultation is finished
            if topic == 'videoconsultation-finished':
                consultation_id = vc_data.get('secret')
                print(f"[🎬 FINISHED] Consultation {consultation_id} finished")
                print(f"[🔐] Patient data will be retrieved securely when recording is processed")

                # Check integration mode
                integration_mode = os.environ.get('INTEGRATION_MODE', 'dual')

                if integration_mode in ['webhook', 'dual']:
                    # Trigger pipeline processing via wrapper script
                    trigger_pipeline_async(consultation_id)
        
        return jsonify({'status': 'success', 'message': 'Webhook processed'})
        
    except Exception as e:
        print(f"[❌ WEBHOOK ERROR] {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/webhook/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'metadata_dir': METADATA_DIR,
        'active_rooms': len(active_rooms),
        'timestamp': datetime.now().isoformat()
    })

# ==========================================
# Prosody Event Sync Endpoints (for speaker diarization)
# ==========================================

# In-memory storage for active rooms
active_rooms = {}

# Recordings directory (same as multitrack recorder)
RECORDINGS_DIR = os.environ.get('RECORDINGS_DIR', '/data')


def get_room_dir(room_name):
    """Get the recording directory for a room"""
    from pathlib import Path
    return Path(RECORDINGS_DIR) / room_name


def save_speaker_mapping(room_name, occupants):
    """Save speaker mapping to the recording directory for diarization"""
    room_dir = get_room_dir(room_name)
    
    # Try multiple possible directories (room might have suffix like -1)
    possible_dirs = [room_dir]
    for i in range(1, 10):
        possible_dirs.append(get_room_dir(f"{room_name}-{i}"))
    
    saved = False
    for dir_path in possible_dirs:
        if dir_path.exists():
            mapping_file = dir_path / 'speaker_mapping.json'
            
            # Create mapping from occupant_jid to name
            mapping = {}
            for occ in occupants:
                jid = occ.get('occupant_jid', '')
                # Extract resource from JID (e.g., "user@domain/resource" -> "resource")
                resource = jid.split('/')[-1] if '/' in jid else jid
                
                mapping[resource] = {
                    'name': occ.get('name', 'Unknown'),
                    'email': occ.get('email'),
                    'id': occ.get('id'),
                    'joined_at': occ.get('joined_at'),
                    'left_at': occ.get('left_at')
                }
            
            with open(mapping_file, 'w') as f:
                json.dump(mapping, f, indent=2)
            
            print(f"[💾 SPEAKER] Saved speaker mapping to {mapping_file}")
            saved = True
    
    if not saved:
        print(f"[⚠️ SPEAKER] Recording directory not found for room: {room_name}")
    
    return saved


@app.route('/events/room/created', methods=['POST'])
def room_created():
    """Handle Prosody room created event"""
    try:
        data = request.get_json()
        room_name = data.get('room_name')
        
        print(f"[🏠 ROOM CREATED] {room_name}")
        
        # Initialize room tracking
        active_rooms[room_name] = {
            'created_at': data.get('created_at'),
            'room_jid': data.get('room_jid'),
            'is_breakout': data.get('is_breakout', False),
            'occupants': []
        }
        
        return jsonify({'status': 'ok', 'message': f'Room {room_name} created'}), 200
        
    except Exception as e:
        print(f"[❌] Error handling room created: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/events/room/destroyed', methods=['POST'])
def room_destroyed():
    """Handle Prosody room destroyed event - save final speaker mapping"""
    try:
        data = request.get_json()
        room_name = data.get('room_name')
        all_occupants = data.get('all_occupants', [])
        
        print(f"[🏚️ ROOM DESTROYED] {room_name} with {len(all_occupants)} total occupants")
        
        # Log all participants
        for occ in all_occupants:
            print(f"  👤 {occ.get('name', 'Unknown')} - joined: {occ.get('joined_at')}, left: {occ.get('left_at')}")
        
        # Save final speaker mapping
        save_speaker_mapping(room_name, all_occupants)
        
        # Clean up active rooms
        if room_name in active_rooms:
            del active_rooms[room_name]
        
        return jsonify({'status': 'ok', 'message': f'Room {room_name} destroyed, speaker mapping saved'}), 200
        
    except Exception as e:
        print(f"[❌] Error handling room destroyed: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/events/occupant/joined', methods=['POST'])
def occupant_joined():
    """Handle Prosody occupant joined event"""
    try:
        data = request.get_json()
        room_name = data.get('room_name')
        occupant = data.get('occupant', {})
        
        name = occupant.get('name', 'Unknown')
        occupant_jid = occupant.get('occupant_jid', '')
        
        print(f"[👤 JOINED] {name} joined {room_name}")
        
        # Update room tracking
        if room_name in active_rooms:
            active_rooms[room_name]['occupants'].append(occupant)
            # Save intermediate speaker mapping
            save_speaker_mapping(room_name, active_rooms[room_name]['occupants'])
        else:
            # Room wasn't tracked, create it now
            active_rooms[room_name] = {
                'created_at': datetime.now().timestamp(),
                'occupants': [occupant]
            }
        
        return jsonify({'status': 'ok', 'message': f'{name} joined {room_name}'}), 200
        
    except Exception as e:
        print(f"[❌] Error handling occupant joined: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/events/occupant/left', methods=['POST'])
def occupant_left():
    """Handle Prosody occupant left event"""
    try:
        data = request.get_json()
        room_name = data.get('room_name')
        occupant = data.get('occupant', {})
        
        name = occupant.get('name', 'Unknown')
        occupant_jid = occupant.get('occupant_jid', '')
        
        print(f"[👋 LEFT] {name} left {room_name}")
        
        # Update room tracking with left_at time
        if room_name in active_rooms:
            for occ in active_rooms[room_name]['occupants']:
                if occ.get('occupant_jid') == occupant_jid:
                    occ['left_at'] = occupant.get('left_at')
                    break
            # Save updated speaker mapping
            save_speaker_mapping(room_name, active_rooms[room_name]['occupants'])
        
        return jsonify({'status': 'ok', 'message': f'{name} left {room_name}'}), 200
        
    except Exception as e:
        print(f"[❌] Error handling occupant left: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/events/rooms', methods=['GET'])
def list_active_rooms():
    """List active rooms (for debugging)"""
    return jsonify(active_rooms), 200

@app.route('/webhook/consultations', methods=['GET'])
def list_consultations():
    """List stored consultation metadata"""
    ensure_metadata_dir()
    
    consultations = []
    for filename in os.listdir(METADATA_DIR):
        if filename.endswith('_metadata.json'):
            filepath = os.path.join(METADATA_DIR, filename)
            try:
                with open(filepath, 'r') as f:
                    metadata = json.load(f)
                    consultations.append({
                        'consultation_id': metadata.get('consultation_id'),
                        'status': metadata.get('status'),
                        'topic': metadata.get('topic'),
                        'recording_processed': metadata.get('recording_processed', False),
                        'webhook_received': metadata.get('webhook_received')
                    })
            except Exception as e:
                print(f"[⚠️] Error reading {filename}: {e}")
    
    return jsonify({'consultations': consultations})

def run_webhook_server():
    """Run the webhook server"""
    port = int(os.environ.get('WEBHOOK_PORT', 9091))
    host = os.environ.get('WEBHOOK_HOST', '0.0.0.0')
    
    print(f"[🌐 WEBHOOK] Starting webhook server on {host}:{port}")
    app.run(host=host, port=port, debug=False)

if __name__ == '__main__':
    run_webhook_server()