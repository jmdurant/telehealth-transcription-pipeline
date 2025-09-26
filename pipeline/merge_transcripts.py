#!/usr/bin/env python3
import sys
import json
import os
import glob

def merge_transcripts(recording_dir):
    """Merge individual transcript files with speaker mapping"""
    
    print(f"[🔀 MERGE] Merging transcripts in {recording_dir}")
    
    # Find all transcript files
    transcript_files = glob.glob(os.path.join(recording_dir, "*_transcript.json"))
    
    if not transcript_files:
        print("[⚠️] No transcript files found")
        return
    
    # Load speaker mapping if available
    speaker_map_file = os.path.join(recording_dir, "speaker_mapping.json")
    speaker_mapping = {}
    
    if os.path.exists(speaker_map_file):
        with open(speaker_map_file, 'r') as f:
            speaker_mapping = json.load(f)
        print(f"[👥] Loaded speaker mapping: {speaker_mapping}")
    
    # Merge all transcripts
    merged_transcript = {
        "recording_id": os.path.basename(recording_dir),
        "speakers": [],
        "full_transcript": []
    }
    
    for transcript_file in sorted(transcript_files):
        with open(transcript_file, 'r') as f:
            data = json.load(f)
        
        # Extract speaker info from filename (e.g., speaker1_transcript.json)
        filename = os.path.basename(transcript_file)
        speaker_id = filename.split('_')[0]
        
        # Get speaker name from mapping or use ID
        speaker_name = speaker_mapping.get(speaker_id, speaker_id)
        
        # Combine all transcript segments
        full_text = " ".join([t.get('text', '') for t in data.get('transcripts', [])])
        
        speaker_data = {
            "speaker_id": speaker_id,
            "speaker_name": speaker_name,
            "file": data.get('file', ''),
            "text": full_text,
            "segments": data.get('transcripts', [])
        }
        
        merged_transcript["speakers"].append(speaker_data)
        
        # Add to full transcript with speaker labels
        for segment in data.get('transcripts', []):
            if 'text' in segment:
                merged_transcript["full_transcript"].append({
                    "speaker": speaker_name,
                    "text": segment['text'],
                    "timestamp": segment.get('timestamp', '')
                })
    
    # Sort full transcript by timestamp if available
    if all('timestamp' in s for s in merged_transcript["full_transcript"]):
        merged_transcript["full_transcript"].sort(key=lambda x: x.get('timestamp', ''))
    
    # Save merged transcript
    output_file = os.path.join(recording_dir, "final_merged.json")
    with open(output_file, 'w') as f:
        json.dump(merged_transcript, f, indent=2)
    
    print(f"[✅] Saved merged transcript to {output_file}")
    
    # Also create a simple text version
    text_output = os.path.join(recording_dir, "transcript.txt")
    with open(text_output, 'w') as f:
        f.write(f"Recording: {merged_transcript['recording_id']}\n")
        f.write("=" * 50 + "\n\n")
        
        for entry in merged_transcript["full_transcript"]:
            f.write(f"{entry['speaker']}: {entry['text']}\n")
        
        f.write("\n" + "=" * 50 + "\n")
        f.write("Individual Speaker Summaries:\n\n")
        
        for speaker in merged_transcript["speakers"]:
            f.write(f"{speaker['speaker_name']}:\n")
            f.write(f"{speaker['text']}\n\n")
    
    print(f"[✅] Saved text transcript to {text_output}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: merge_transcripts.py <recording_dir>")
        sys.exit(1)
    
    merge_transcripts(sys.argv[1])