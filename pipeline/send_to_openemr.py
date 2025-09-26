#!/usr/bin/env python3
import sys
import os
import requests
import json
from datetime import datetime

OPENEMR_API_URL = os.environ.get("OPENEMR_API_URL", "http://openemr:80/apis/default/api")
OPENEMR_API_KEY = os.environ.get("OPENEMR_API_KEY", "")
PATIENT_ID = os.environ.get("PATIENT_ID", "")

def send_to_openemr(note_file):
    """Send clinical note to OpenEMR via API"""
    
    print(f"[📋 EMR] Sending note to OpenEMR from {note_file}")
    
    # Read the clinical note
    with open(note_file, 'r') as f:
        note_content = f.read()
    
    # Extract recording ID from directory name
    recording_dir = os.path.dirname(note_file)
    recording_id = os.path.basename(recording_dir)
    
    # Prepare note data
    note_data = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "time": datetime.now().strftime("%H:%M:%S"),
        "title": f"Telehealth Consultation - {recording_id}",
        "body": note_content,
        "category": "telehealth",
        "type": "clinical_note",
        "metadata": {
            "recording_id": recording_id,
            "source": "telehealth_transcription_pipeline"
        }
    }
    
    # Headers for API request
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    if OPENEMR_API_KEY:
        headers["Authorization"] = f"Bearer {OPENEMR_API_KEY}"
    
    try:
        # Determine endpoint based on patient ID availability
        if PATIENT_ID:
            # Add note to specific patient
            endpoint = f"{OPENEMR_API_URL}/patient/{PATIENT_ID}/document"
            note_data["pid"] = PATIENT_ID
        else:
            # Add to unassigned notes queue
            endpoint = f"{OPENEMR_API_URL}/document/unassigned"
        
        # Send to OpenEMR
        response = requests.post(endpoint, json=note_data, headers=headers)
        
        if response.status_code in [200, 201]:
            result = response.json()
            document_id = result.get('document_id', 'unknown')
            print(f"[✅] Successfully sent to OpenEMR. Document ID: {document_id}")
            
            # Save confirmation
            confirmation_file = os.path.join(recording_dir, "openemr_upload.json")
            with open(confirmation_file, 'w') as f:
                json.dump({
                    "status": "success",
                    "document_id": document_id,
                    "timestamp": datetime.now().isoformat(),
                    "patient_id": PATIENT_ID or "unassigned"
                }, f, indent=2)
                
        else:
            print(f"[❌] Error from OpenEMR API: {response.status_code}")
            print(response.text)
            
            # Save error details
            error_file = os.path.join(recording_dir, "openemr_error.json")
            with open(error_file, 'w') as f:
                json.dump({
                    "status": "error",
                    "status_code": response.status_code,
                    "error": response.text,
                    "timestamp": datetime.now().isoformat()
                }, f, indent=2)
            
    except Exception as e:
        print(f"[❌] Error sending to OpenEMR: {e}")
        
        # Save error details
        error_file = os.path.join(recording_dir, "openemr_error.json")
        with open(error_file, 'w') as f:
            json.dump({
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }, f, indent=2)
    
    # Alternative: Save to shared directory for manual import
    shared_dir = os.environ.get("SHARED_NOTES_DIR", "/shared/notes")
    if os.path.exists(shared_dir):
        try:
            # Create filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            shared_filename = f"telehealth_note_{recording_id}_{timestamp}.txt"
            shared_path = os.path.join(shared_dir, shared_filename)
            
            # Copy note to shared directory
            with open(note_file, 'r') as src:
                with open(shared_path, 'w') as dst:
                    dst.write(src.read())
            
            print(f"[📁] Also saved to shared directory: {shared_path}")
            
        except Exception as e:
            print(f"[⚠️] Could not save to shared directory: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: send_to_openemr.py <note_file>")
        sys.exit(1)
    
    send_to_openemr(sys.argv[1])