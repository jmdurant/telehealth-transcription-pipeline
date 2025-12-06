#!/bin/bash
# Finalize script for multitrack recording with diarization support
# Called by multitrack recorder when recording session ends

RECORDING_DIR="$1"
MEETING_ID=$(basename "$RECORDING_DIR")

echo "[📁 FINALIZE] Processing $RECORDING_DIR"
echo "[🔑] Meeting ID: $MEETING_ID"

# Check if speaker mapping exists (from Prosody events)
SPEAKER_MAPPING="$RECORDING_DIR/speaker_mapping.json"
if [ -f "$SPEAKER_MAPPING" ]; then
    echo "[👥] Speaker mapping found - diarization enabled"
    cat "$SPEAKER_MAPPING"
else
    echo "[⚠️] No speaker mapping found - will use generic labels"
fi

# Step 1: Extract individual tracks from MKA for diarization
echo "[🎵] Extracting audio tracks from MKA..."
for f in "$RECORDING_DIR"/*.mka; do
    if [ -f "$f" ]; then
        base=$(basename "$f" .mka)
        
        # Get number of audio streams in the MKA
        STREAM_COUNT=$(ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 "$f" 2>/dev/null | wc -l)
        echo "[📊] Found $STREAM_COUNT audio streams in $f"
        
        if [ "$STREAM_COUNT" -gt 1 ]; then
            # Extract each stream separately for diarization
            for i in $(seq 0 $((STREAM_COUNT - 1))); do
                OUTPUT_FILE="$RECORDING_DIR/speaker${i}.wav"
                echo "[🎤] Extracting stream $i to $OUTPUT_FILE"
                ffmpeg -y -i "$f" -map 0:a:$i -ac 1 -ar 16000 "$OUTPUT_FILE" 2>/dev/null
            done
        else
            # Single stream - just convert to WAV
            echo "[🎤] Single stream - converting to WAV"
            ffmpeg -y -i "$f" -ac 1 -ar 16000 "$RECORDING_DIR/${base}.wav" 2>/dev/null
        fi
    fi
done

# Step 2: Transcribe each audio file
echo "[🗣️] Transcribing audio files..."
for wav in "$RECORDING_DIR"/*.wav; do
    if [ -f "$wav" ]; then
        echo "[📝] Transcribing: $wav"
        python3 /pipeline/send_to_parakeet.py "$wav"
    fi
done

# Step 3: Retrieve consultation data from telesalud
echo "[🏥] Retrieving consultation data..."
python3 /pipeline/telesalud_api_client.py "$MEETING_ID"

# Step 4: Map endpoints if available
if [ -f "/logs/${MEETING_ID}.json" ]; then
    echo "[🗺️] Mapping endpoints..."
    python3 /pipeline/map_endpoints.py "/logs/${MEETING_ID}.json"
fi

# Step 5: Merge transcripts with speaker labels
echo "[🔀] Merging transcripts with speaker labels..."
python3 /pipeline/merge_transcripts.py "$RECORDING_DIR"

# Step 6: Summarize with Ollama
echo "[🤖] Generating AI summary..."
if [ -f "$RECORDING_DIR/final_merged.json" ]; then
    python3 /pipeline/summarize_with_ollama.py "$RECORDING_DIR/final_merged.json"
else
    echo "[⚠️] No merged transcript found, skipping summarization"
fi

# Step 7: Send to telesalud evolution field
echo "[📤] Sending to telesalud..."
if [ -f "$RECORDING_DIR/final_note.txt" ]; then
    python3 /pipeline/send_to_telesalud.py "$RECORDING_DIR/final_note.txt"
else
    echo "[⚠️] No final note found, skipping telesalud update"
fi

# Optional step if pushing directly to OpenEMR
# python3 /pipeline/send_to_openemr.py "$RECORDING_DIR/final_note.txt"

echo "[✅ COMPLETE] Finalized pipeline for $RECORDING_DIR"