#!/usr/bin/env python3
import sys
import json
import os
import requests

OLLAMA_API_URL = os.environ.get("OLLAMA_API_URL", "http://ollama:11434/api/generate")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")

def load_consultation_metadata(transcript_file):
    """Load consultation metadata including doctor notes"""
    recording_dir = os.path.dirname(transcript_file)
    recording_id = os.path.basename(recording_dir)
    
    # Look for metadata file
    metadata_dir = os.environ.get("METADATA_DIR", "/shared/consultations")
    if os.path.exists(metadata_dir):
        for filename in os.listdir(metadata_dir):
            if filename.endswith('_metadata.json'):
                filepath = os.path.join(metadata_dir, filename)
                try:
                    with open(filepath, 'r') as f:
                        metadata = json.load(f)
                    
                    consultation_id = metadata.get('consultation_id', '')
                    if (consultation_id in recording_id or 
                        recording_id in consultation_id):
                        return metadata
                except Exception as e:
                    print(f"[⚠️] Error reading metadata {filename}: {e}")
    
    return None

def summarize_with_ollama(transcript_file):
    """Generate clinical summary using Ollama LLM"""
    
    print(f"[🤖 LLM] Generating summary from {transcript_file}")
    
    # Load transcript
    with open(transcript_file, 'r') as f:
        transcript_data = json.load(f)
    
    # Load consultation metadata for doctor notes
    metadata = load_consultation_metadata(transcript_file)
    doctor_notes = ""
    patient_name = "Patient"
    medic_name = "Doctor"
    
    if metadata:
        doctor_notes = metadata.get('doctor_notes', '')
        patient_name = metadata.get('patient_name', 'Patient')
        medic_name = metadata.get('medic_name', 'Doctor')
        print(f"[📋] Found consultation metadata for {patient_name} with {medic_name}")
        if doctor_notes:
            print(f"[📝] Including doctor's typed notes in summary")
    
    # Prepare conversation text
    conversation_text = ""
    for entry in transcript_data.get('full_transcript', []):
        speaker = entry.get('speaker', 'Unknown')
        text = entry.get('text', '')
        conversation_text += f"{speaker}: {text}\n"
    
    # Prepare enhanced prompt with doctor notes
    prompt = f"""You are a medical assistant helping to summarize a telehealth consultation between {medic_name} and {patient_name}.

Please provide a structured clinical summary combining the audio conversation transcript and the doctor's typed notes.

Include sections for:
1. Chief Complaint
2. History of Present Illness
3. Review of Systems (if mentioned)
4. Assessment
5. Plan/Recommendations
6. Follow-up (if discussed)

Keep the summary professional, concise, and clinically relevant. Integrate information from both the conversation and the doctor's notes seamlessly.

Audio Conversation Transcript:
{conversation_text}

Doctor's Typed Notes:
{doctor_notes if doctor_notes else "No additional typed notes provided."}

Clinical Summary:"""
    
    # Call Ollama API
    try:
        response = requests.post(OLLAMA_API_URL, json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "temperature": 0.3,  # Lower temperature for more consistent output
            "max_tokens": 1000
        })
        
        if response.status_code == 200:
            result = response.json()
            summary = result.get('response', '')
            
            # Save summary
            recording_dir = os.path.dirname(transcript_file)
            
            # Save as JSON
            summary_data = {
                "recording_id": transcript_data.get('recording_id'),
                "model": OLLAMA_MODEL,
                "summary": summary,
                "metadata": {
                    "total_speakers": len(transcript_data.get('speakers', [])),
                    "total_segments": len(transcript_data.get('full_transcript', [])),
                    "patient_name": patient_name,
                    "medic_name": medic_name,
                    "doctor_notes_included": bool(doctor_notes),
                    "sources": ["audio_transcript", "doctor_notes"] if doctor_notes else ["audio_transcript"]
                }
            }
            
            json_output = os.path.join(recording_dir, "clinical_summary.json")
            with open(json_output, 'w') as f:
                json.dump(summary_data, f, indent=2)
            
            # Save as text
            text_output = os.path.join(recording_dir, "final_note.txt")
            with open(text_output, 'w') as f:
                f.write(f"Telehealth Consultation Summary\n")
                f.write(f"Patient: {patient_name}\n")
                f.write(f"Provider: {medic_name}\n")
                f.write(f"Recording ID: {transcript_data.get('recording_id')}\n")
                f.write("=" * 50 + "\n\n")
                f.write(summary)
                f.write("\n\n" + "=" * 50 + "\n")
                f.write(f"Generated by: {OLLAMA_MODEL}\n")
                if doctor_notes:
                    f.write("Sources: Audio transcript + Doctor's typed notes\n")
                else:
                    f.write("Sources: Audio transcript only\n")
            
            print(f"[✅] Saved summary to {text_output}")
            
        else:
            print(f"[❌] Error from Ollama API: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"[❌] Error calling Ollama: {e}")
        
        # Fallback: Create a basic summary
        recording_dir = os.path.dirname(transcript_file)
        text_output = os.path.join(recording_dir, "final_note.txt")
        
        with open(text_output, 'w') as f:
            f.write(f"Telehealth Consultation Transcript\n")
            f.write(f"Recording ID: {transcript_data.get('recording_id')}\n")
            f.write("=" * 50 + "\n\n")
            f.write("Note: Automated summary generation failed. Full transcript below:\n\n")
            f.write(conversation_text)
        
        print(f"[⚠️] Saved transcript without summary to {text_output}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: summarize_with_ollama.py <transcript_file>")
        sys.exit(1)
    
    summarize_with_ollama(sys.argv[1])