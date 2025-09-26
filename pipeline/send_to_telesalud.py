#!/usr/bin/env python3
"""
Send clinical notes to telesalud module via evolution field API
"""
import sys
import os
import json
import requests
from datetime import datetime

TELESALUD_API_URL = os.environ.get("TELESALUD_API_URL", "http://telesalud-web/videoconsultation/evolution")
TELESALUD_WEBHOOK_URL = os.environ.get("TELESALUD_WEBHOOK_URL", "http://telesalud-web/api/webhook/evolution")
USE_WEBHOOK = os.environ.get("USE_WEBHOOK", "true").lower() == "true"
METADATA_DIR = os.environ.get("METADATA_DIR", "/shared/consultations")

def find_consultation_metadata(recording_dir):
    """Find consultation metadata based on recording directory"""
    
    # Extract potential consultation ID from recording directory name
    recording_id = os.path.basename(recording_dir)
    
    # Look for metadata files
    metadata_files = []
    if os.path.exists(METADATA_DIR):
        for filename in os.listdir(METADATA_DIR):
            if filename.endswith('_metadata.json'):
                filepath = os.path.join(METADATA_DIR, filename)
                try:
                    with open(filepath, 'r') as f:
                        metadata = json.load(f)
                        
                    # Match by consultation ID or recording pattern
                    consultation_id = metadata.get('consultation_id', '')
                    if (consultation_id in recording_id or 
                        recording_id in consultation_id or
                        consultation_id == recording_id):
                        return metadata, filepath
                        
                    metadata_files.append((metadata, filepath))
                        
                except Exception as e:
                    print(f"[⚠️] Error reading metadata {filename}: {e}")
    
    # If no exact match, try to find the most recent unprocessed consultation
    if metadata_files:
        print(f"[🔍] No exact match for {recording_id}, looking for recent unprocessed consultation")
        
        # Sort by webhook received time and find unprocessed
        unprocessed = [
            (meta, path) for meta, path in metadata_files 
            if not meta.get('recording_processed', False)
        ]
        
        if unprocessed:
            # Sort by webhook received time (most recent first)
            unprocessed.sort(key=lambda x: x[0].get('webhook_received', ''), reverse=True)
            print(f"[📋] Using most recent unprocessed consultation: {unprocessed[0][0].get('consultation_id')}")
            return unprocessed[0]
    
    print(f"[⚠️] No consultation metadata found for recording {recording_id}")
    return None, None

def send_to_telesalud_webhook(note_file, metadata):
    """Send clinical note via webhook endpoint"""
    consultation_id = metadata.get('consultation_id')
    
    # Read the clinical note
    with open(note_file, 'r') as f:
        note_content = f.read()
    
    # Prepare webhook payload
    webhook_data = {
        'consultation_id': consultation_id,
        'evolution': note_content,
        'metadata': {
            'patient_name': metadata.get('patient_name'),
            'patient_id': metadata.get('patient_id'),
            'medic_name': metadata.get('medic_name'),
            'appointment_date': metadata.get('appointment_date'),
            'recording_processed': True,
            'source': 'transcription_pipeline',
            'timestamp': datetime.now().isoformat()
        }
    }
    
    # Add webhook token if configured
    headers = {'Content-Type': 'application/json'}
    webhook_token = os.environ.get('WEBHOOK_TOKEN')
    if webhook_token:
        headers['Authorization'] = f'Bearer {webhook_token}'
    
    print(f"[🌐] Sending to telesalud webhook: {TELESALUD_WEBHOOK_URL}")
    print(f"[🔑] Consultation ID: {consultation_id}")
    
    response = requests.post(TELESALUD_WEBHOOK_URL, json=webhook_data, headers=headers, timeout=30)
    return response

def send_to_telesalud_form(note_file, metadata):
    """Send clinical note via form endpoint (legacy method)"""
    consultation_id = metadata.get('consultation_id')
    medic_secret = metadata.get('medic_secret')
    
    # Read the clinical note
    with open(note_file, 'r') as f:
        note_content = f.read()
    
    # Prepare API request
    api_data = {
        'vc': consultation_id,
        'medic': medic_secret,
        'evolution': note_content,
        'doctor_notes': note_content  # For backward compatibility
    }
    
    print(f"[🌐] Sending to telesalud form API: {TELESALUD_API_URL}")
    print(f"[🔑] Consultation ID: {consultation_id}")
    
    response = requests.post(TELESALUD_API_URL, data=api_data, timeout=30)
    return response

def send_to_telesalud(note_file):
    """Send clinical note to telesalud evolution field"""
    
    print(f"[📋 TELESALUD] Sending note to telesalud from {note_file}")
    
    # Get recording directory
    recording_dir = os.path.dirname(note_file)
    
    # Find consultation metadata
    metadata, metadata_file = find_consultation_metadata(recording_dir)
    if not metadata:
        print("[❌] Cannot send to telesalud: No consultation metadata found")
        return False
    
    consultation_id = metadata.get('consultation_id')
    
    if not consultation_id:
        print("[❌] Cannot send to telesalud: Missing consultation_id")
        return False
    
    try:
        # Choose method based on configuration
        if USE_WEBHOOK:
            response = send_to_telesalud_webhook(note_file, metadata)
        else:
            medic_secret = metadata.get('medic_secret')
            if not medic_secret:
                print("[❌] Cannot use form method: Missing medic_secret")
                return False
            response = send_to_telesalud_form(note_file, metadata)
        
        if response.status_code == 200:
            print(f"[✅] Successfully sent to telesalud")
            
            # Mark consultation as processed
            metadata['recording_processed'] = True
            metadata['evolution_sent'] = datetime.now().isoformat()
            metadata['evolution_response'] = response.text
            
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            # Save confirmation
            confirmation_file = os.path.join(recording_dir, "telesalud_upload.json")
            with open(confirmation_file, 'w') as f:
                json.dump({
                    "status": "success",
                    "consultation_id": consultation_id,
                    "timestamp": datetime.now().isoformat(),
                    "response": response.text
                }, f, indent=2)
            
            return True
            
        else:
            print(f"[❌] Error from telesalud API: {response.status_code}")
            print(f"Response: {response.text}")
            
            # Save error details
            error_file = os.path.join(recording_dir, "telesalud_error.json")
            with open(error_file, 'w') as f:
                json.dump({
                    "status": "error",
                    "status_code": response.status_code,
                    "error": response.text,
                    "consultation_id": consultation_id,
                    "timestamp": datetime.now().isoformat()
                }, f, indent=2)
            
            return False
            
    except Exception as e:
        print(f"[❌] Error sending to telesalud: {e}")
        
        # Save error details
        error_file = os.path.join(recording_dir, "telesalud_error.json")
        with open(error_file, 'w') as f:
            json.dump({
                "status": "error",
                "error": str(e),
                "consultation_id": consultation_id,
                "timestamp": datetime.now().isoformat()
            }, f, indent=2)
        
        return False

def get_consultation_info(recording_dir):
    """Get consultation information for a recording directory"""
    metadata, _ = find_consultation_metadata(recording_dir)
    if metadata:
        return {
            'consultation_id': metadata.get('consultation_id'),
            'patient_name': metadata.get('patient_name'),
            'patient_id': metadata.get('patient_id'),
            'medic_name': metadata.get('medic_name'),
            'status': metadata.get('status'),
            'recording_processed': metadata.get('recording_processed', False)
        }
    return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: send_to_telesalud.py <note_file> [--info]")
        print("       send_to_telesalud.py <recording_dir> --info")
        sys.exit(1)
    
    if '--info' in sys.argv:
        # Show consultation info
        path = sys.argv[1]
        if os.path.isfile(path):
            path = os.path.dirname(path)
        
        info = get_consultation_info(path)
        if info:
            print(json.dumps(info, indent=2))
        else:
            print("No consultation metadata found")
    else:
        # Send note
        send_to_telesalud(sys.argv[1])