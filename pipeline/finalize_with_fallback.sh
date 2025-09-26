#!/bin/bash
# Enhanced finalize script with smart audio processing
# Tries to send MKA directly to Parakeet, falls back to WAV conversion if needed

RECORDING_DIR="$1"
echo "[📁 FINALIZE] Processing $RECORDING_DIR"

# Environment variable to control audio processing mode
# Options: auto (default), mka_only, wav_only
AUDIO_PROCESSING_MODE="${AUDIO_PROCESSING_MODE:-auto}"
PARAKEET_ACCEPTS_MKA="${PARAKEET_ACCEPTS_MKA:-unknown}"

echo "[🎵] Audio processing mode: $AUDIO_PROCESSING_MODE"

process_audio_files() {
    local dir="$1"

    if [ "$AUDIO_PROCESSING_MODE" = "wav_only" ]; then
        # Force WAV conversion (original behavior)
        echo "[🔄] Converting MKA files to WAV (wav_only mode)..."
        for f in "$dir"/*.mka; do
            [ -f "$f" ] || continue
            base=$(basename "$f" .mka)
            echo "  Converting $base.mka → $base.wav"
            ffmpeg -y -i "$f" -ac 1 -ar 16000 "$dir/${base}.wav" 2>/dev/null || {
                echo "[❌] Failed to convert $f"
                return 1
            }
        done

        # Send WAV files to Parakeet
        for wav in "$dir"/*.wav; do
            [ -f "$wav" ] || continue
            python3 /pipeline/send_to_parakeet.py "$wav"
        done

    elif [ "$AUDIO_PROCESSING_MODE" = "mka_only" ]; then
        # Only try MKA, no fallback
        echo "[📤] Sending MKA files directly to Parakeet (mka_only mode)..."
        for mka in "$dir"/*.mka; do
            [ -f "$mka" ] || continue
            python3 /pipeline/send_to_parakeet.py "$mka" || {
                echo "[❌] Parakeet doesn't accept MKA files. Set AUDIO_PROCESSING_MODE=wav_only"
                return 1
            }
        done

    else  # auto mode (default)
        echo "[🤖] Auto-detecting Parakeet capabilities..."

        # Try sending first MKA file to test if Parakeet accepts it
        local test_file=""
        for mka in "$dir"/*.mka; do
            [ -f "$mka" ] && test_file="$mka" && break
        done

        if [ -n "$test_file" ]; then
            echo "[🧪] Testing with $test_file..."

            # Try sending MKA directly
            if python3 /pipeline/send_to_parakeet.py "$test_file" 2>/tmp/parakeet_test.log; then
                echo "[✅] Parakeet accepts MKA files! Processing remaining files..."
                PARAKEET_ACCEPTS_MKA="yes"

                # Process remaining MKA files
                for mka in "$dir"/*.mka; do
                    [ -f "$mka" ] || continue
                    [ "$mka" = "$test_file" ] && continue  # Skip already processed test file
                    python3 /pipeline/send_to_parakeet.py "$mka"
                done

            else
                echo "[⚠️] Parakeet doesn't accept MKA, falling back to WAV conversion..."
                PARAKEET_ACCEPTS_MKA="no"

                # Convert all MKA to WAV
                for f in "$dir"/*.mka; do
                    [ -f "$f" ] || continue
                    base=$(basename "$f" .mka)
                    echo "  Converting $base.mka → $base.wav"
                    ffmpeg -y -i "$f" -ac 1 -ar 16000 "$dir/${base}.wav" 2>/dev/null
                done

                # Send all WAV files
                for wav in "$dir"/*.wav; do
                    [ -f "$wav" ] || continue
                    python3 /pipeline/send_to_parakeet.py "$wav"
                done
            fi
        else
            echo "[⚠️] No MKA files found in $dir"
        fi
    fi
}

# Process audio files with smart fallback
process_audio_files "$RECORDING_DIR"

# Continue with rest of pipeline
echo "[🔍] Retrieving consultation metadata..."
python3 /pipeline/telesalud_api_client.py "$(basename $RECORDING_DIR)"

echo "[🗺️] Mapping speakers..."
python3 /pipeline/map_endpoints.py "/logs/$(basename $RECORDING_DIR).json"

echo "[🔀] Merging transcripts..."
python3 /pipeline/merge_transcripts.py "$RECORDING_DIR"

echo "[🤖] Generating summary..."
python3 /pipeline/summarize_with_ollama.py "$RECORDING_DIR/final_merged.json"

echo "[📤] Sending to telesalud..."
python3 /pipeline/send_to_telesalud.py "$RECORDING_DIR/final_note.txt"

# Optional: Send to OpenEMR
# python3 /pipeline/send_to_openemr.py "$RECORDING_DIR/final_note.txt"

echo "[✅ COMPLETE] Finalized pipeline for $RECORDING_DIR"
echo "[📊] Audio processing used: ${PARAKEET_ACCEPTS_MKA:-unknown}"