#!/bin/bash
# Wrapper script that can be called either by Jitsi directly or via webhook
# Supports both automatic (Jitsi finalize_script) and webhook-triggered modes
# Includes locking mechanism to prevent duplicate processing in dual mode

RECORDING_DIR="$1"
TRIGGER_SOURCE="${2:-jitsi}"  # Default to 'jitsi' if not specified
CONSULTATION_ID="${3:-}"      # Optional consultation ID from webhook

echo "[🎬 FINALIZE WRAPPER] Starting processing"
echo "  Recording Directory: $RECORDING_DIR"
echo "  Trigger Source: $TRIGGER_SOURCE"
echo "  Consultation ID: ${CONSULTATION_ID:-auto-detect}"

# Validate recording directory
if [ -z "$RECORDING_DIR" ]; then
    echo "[❌] Error: No recording directory provided"
    exit 1
fi

if [ ! -d "$RECORDING_DIR" ]; then
    echo "[❌] Error: Recording directory does not exist: $RECORDING_DIR"
    exit 1
fi

# Extract consultation ID from directory name if not provided
if [ -z "$CONSULTATION_ID" ]; then
    CONSULTATION_ID=$(basename "$RECORDING_DIR")
    echo "[🔍] Extracted consultation ID from path: $CONSULTATION_ID"
fi

# Setup directories and lock file
METADATA_DIR="${METADATA_DIR:-/shared/consultations}"
mkdir -p "$METADATA_DIR"
LOCK_FILE="$METADATA_DIR/${CONSULTATION_ID}.lock"

# Attempt to acquire lock using atomic mkdir
if ! mkdir "$LOCK_FILE" 2>/dev/null; then
    echo "[🔒] Processing already in progress for consultation $CONSULTATION_ID"
    echo "[📊] Checking current processing status..."

    # Check if there's a processing file to see the status
    PROCESSING_FILE="$METADATA_DIR/${CONSULTATION_ID}_processing.json"
    if [ -f "$PROCESSING_FILE" ]; then
        echo "[📋] Current status:"
        cat "$PROCESSING_FILE"
    fi

    echo "[⏭️] Skipping duplicate trigger from: $TRIGGER_SOURCE"
    exit 0
fi

echo "[🔓] Lock acquired successfully for consultation $CONSULTATION_ID"

# Set up cleanup trap to remove lock on exit
cleanup() {
    local exit_code=$?
    echo "[🧹] Cleaning up lock file for consultation $CONSULTATION_ID"
    rmdir "$LOCK_FILE" 2>/dev/null || true
    exit $exit_code
}
trap cleanup EXIT INT TERM

# Create processing log entry
cat > "$METADATA_DIR/${CONSULTATION_ID}_processing.json" <<EOF
{
  "consultation_id": "$CONSULTATION_ID",
  "recording_dir": "$RECORDING_DIR",
  "trigger_source": "$TRIGGER_SOURCE",
  "processing_started": "$(date -Iseconds)",
  "status": "processing"
}
EOF

# Call the appropriate finalize script based on configuration
AUDIO_PROCESSING_MODE="${AUDIO_PROCESSING_MODE:-auto}"

if [ -f "/pipeline/finalize_with_fallback.sh" ] && [ "$AUDIO_PROCESSING_MODE" != "legacy" ]; then
    echo "[🚀] Executing enhanced pipeline with fallback support..."
    /pipeline/finalize_with_fallback.sh "$RECORDING_DIR"
    RESULT=$?
else
    echo "[🚀] Executing standard pipeline..."
    /pipeline/finalize.sh "$RECORDING_DIR"
    RESULT=$?
fi

# Update processing status
if [ $RESULT -eq 0 ]; then
    STATUS="completed"
    echo "[✅] Pipeline completed successfully"
else
    STATUS="failed"
    echo "[❌] Pipeline failed with exit code: $RESULT"
fi

# Update processing log
cat > "$METADATA_DIR/${CONSULTATION_ID}_processing.json" <<EOF
{
  "consultation_id": "$CONSULTATION_ID",
  "recording_dir": "$RECORDING_DIR",
  "trigger_source": "$TRIGGER_SOURCE",
  "processing_started": "$(date -Iseconds)",
  "processing_completed": "$(date -Iseconds)",
  "status": "$STATUS",
  "exit_code": $RESULT
}
EOF

# If triggered by webhook, notify webhook handler of completion
if [ "$TRIGGER_SOURCE" = "webhook" ] && [ -n "$WEBHOOK_CALLBACK_URL" ]; then
    echo "[📡] Notifying webhook handler of completion..."
    curl -X POST "$WEBHOOK_CALLBACK_URL" \
        -H "Content-Type: application/json" \
        -d "{\"consultation_id\":\"$CONSULTATION_ID\",\"status\":\"$STATUS\"}" \
        2>/dev/null || echo "[⚠️] Could not notify webhook handler"
fi

exit $RESULT