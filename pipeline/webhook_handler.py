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
        'timestamp': datetime.now().isoformat()
    })

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