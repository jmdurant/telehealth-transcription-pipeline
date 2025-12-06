#!/usr/bin/env python3
"""
Event Handler for Prosody Event Sync
Receives room/occupant events and maintains speaker mapping for diarization
"""
import os
import json
import logging
from datetime import datetime
from flask import Flask, request, jsonify
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Directory where recordings are stored (same as multitrack recorder)
RECORDINGS_DIR = os.environ.get('RECORDINGS_DIR', '/data')
# Directory for shared consultation metadata
METADATA_DIR = os.environ.get('METADATA_DIR', '/shared/consultations')

# In-memory storage for active rooms (will be persisted to disk)
active_rooms = {}


def get_room_dir(room_name):
    """Get the recording directory for a room"""
    return Path(RECORDINGS_DIR) / room_name


def get_metadata_dir():
    """Get the metadata directory"""
    path = Path(METADATA_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_speaker_mapping(room_name, occupants):
    """Save speaker mapping to the recording directory"""
    # Save to recording directory (for finalize script)
    room_dir = get_room_dir(room_name)
    if room_dir.exists():
        mapping_file = room_dir / 'speaker_mapping.json'
        
        # Create mapping from occupant_jid to name
        mapping = {}
        for occ in occupants:
            # Use the JID's resource part as the track identifier
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
        
        logger.info(f"[💾] Saved speaker mapping to {mapping_file}")
        return True
    else:
        logger.warning(f"[⚠️] Recording directory not found: {room_dir}")
        return False


def save_room_metadata(room_name, data):
    """Save room metadata to shared directory"""
    metadata_dir = get_metadata_dir()
    metadata_file = metadata_dir / f'{room_name}_room.json'
    
    with open(metadata_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    logger.info(f"[💾] Saved room metadata to {metadata_file}")


@app.route('/events/room/created', methods=['POST'])
def room_created():
    """Handle room created event"""
    try:
        data = request.get_json()
        room_name = data.get('room_name')
        
        logger.info(f"[🏠 ROOM CREATED] {room_name}")
        logger.debug(f"  Payload: {json.dumps(data, indent=2)}")
        
        # Initialize room tracking
        active_rooms[room_name] = {
            'created_at': data.get('created_at'),
            'room_jid': data.get('room_jid'),
            'is_breakout': data.get('is_breakout', False),
            'occupants': []
        }
        
        # Save initial metadata
        save_room_metadata(room_name, active_rooms[room_name])
        
        return jsonify({'status': 'ok', 'message': f'Room {room_name} created'}), 200
        
    except Exception as e:
        logger.error(f"[❌] Error handling room created: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/events/room/destroyed', methods=['POST'])
def room_destroyed():
    """Handle room destroyed event - save final speaker mapping"""
    try:
        data = request.get_json()
        room_name = data.get('room_name')
        all_occupants = data.get('all_occupants', [])
        
        logger.info(f"[🏚️ ROOM DESTROYED] {room_name} with {len(all_occupants)} total occupants")
        
        # Log all participants for debugging
        for occ in all_occupants:
            logger.info(f"  👤 {occ.get('name', 'Unknown')} - joined: {occ.get('joined_at')}, left: {occ.get('left_at')}")
        
        # Save final speaker mapping
        save_speaker_mapping(room_name, all_occupants)
        
        # Update room metadata
        room_data = active_rooms.get(room_name, {})
        room_data['destroyed_at'] = data.get('destroyed_at')
        room_data['all_occupants'] = all_occupants
        save_room_metadata(room_name, room_data)
        
        # Clean up active rooms
        if room_name in active_rooms:
            del active_rooms[room_name]
        
        return jsonify({'status': 'ok', 'message': f'Room {room_name} destroyed, speaker mapping saved'}), 200
        
    except Exception as e:
        logger.error(f"[❌] Error handling room destroyed: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/events/occupant/joined', methods=['POST'])
def occupant_joined():
    """Handle occupant joined event"""
    try:
        data = request.get_json()
        room_name = data.get('room_name')
        occupant = data.get('occupant', {})
        
        name = occupant.get('name', 'Unknown')
        occupant_jid = occupant.get('occupant_jid', '')
        
        logger.info(f"[👤 JOINED] {name} joined {room_name}")
        logger.debug(f"  JID: {occupant_jid}")
        
        # Update room tracking
        if room_name in active_rooms:
            active_rooms[room_name]['occupants'].append(occupant)
            # Save intermediate speaker mapping (in case room doesn't get destroyed cleanly)
            save_speaker_mapping(room_name, active_rooms[room_name]['occupants'])
        
        return jsonify({'status': 'ok', 'message': f'{name} joined {room_name}'}), 200
        
    except Exception as e:
        logger.error(f"[❌] Error handling occupant joined: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/events/occupant/left', methods=['POST'])
def occupant_left():
    """Handle occupant left event"""
    try:
        data = request.get_json()
        room_name = data.get('room_name')
        occupant = data.get('occupant', {})
        
        name = occupant.get('name', 'Unknown')
        occupant_jid = occupant.get('occupant_jid', '')
        
        logger.info(f"[👋 LEFT] {name} left {room_name}")
        
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
        logger.error(f"[❌] Error handling occupant left: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'active_rooms': len(active_rooms),
        'recordings_dir': RECORDINGS_DIR,
        'metadata_dir': METADATA_DIR
    }), 200


@app.route('/rooms', methods=['GET'])
def list_rooms():
    """List active rooms (for debugging)"""
    return jsonify(active_rooms), 200


if __name__ == '__main__':
    port = int(os.environ.get('EVENT_HANDLER_PORT', 9091))
    logger.info(f"[🚀] Starting Event Handler on port {port}")
    logger.info(f"[📁] Recordings directory: {RECORDINGS_DIR}")
    logger.info(f"[📁] Metadata directory: {METADATA_DIR}")
    
    app.run(host='0.0.0.0', port=port, debug=False)
