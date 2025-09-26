#!/bin/bash
RECORDING_DIR="$1"
echo "[📁 FINALIZE] Processing $RECORDING_DIR"

for f in "$RECORDING_DIR"/*.mka; do
  base=$(basename "$f" .mka)
  ffmpeg -y -i "$f" -ac 1 -ar 16000 "$RECORDING_DIR/${base}.wav"
done

for wav in "$RECORDING_DIR"/*.wav; do
  python3 /pipeline/send_to_parakeet.py "$wav"
done

# Securely retrieve consultation data via authenticated API
python3 /pipeline/telesalud_api_client.py "$(basename $RECORDING_DIR)"

python3 /pipeline/map_endpoints.py "/logs/$(basename $RECORDING_DIR).json"
python3 /pipeline/merge_transcripts.py "$RECORDING_DIR"
python3 /pipeline/summarize_with_ollama.py "$RECORDING_DIR/final_merged.json"
# Send to telesalud evolution field
python3 /pipeline/send_to_telesalud.py "$RECORDING_DIR/final_note.txt"

# Optional step if pushing directly to OpenEMR
# python3 /pipeline/send_to_openemr.py "$RECORDING_DIR/final_note.txt"
echo "[✅ COMPLETE] Finalized pipeline for $RECORDING_DIR"