# Telehealth Audio Transcription and Summarization Pipeline

A complete, self-hosted transcription and summarization pipeline for telehealth visits using Jitsi Meet, Parakeet ASR, and Ollama LLM.

## Architecture Overview

```
[ Jitsi Meet ] → [ Jitsi Recorder (.mka) ]
                      ↓
              finalize.sh (pipeline)
                      ↓
           [ Parakeet ASR (WebSocket) ]
                      ↓
           [ Speaker Mapping from Prosody ]
                      ↓
           [ Merged Transcript ]
                      ↓
            [ Ollama / llama.cpp Summary ]
                      ↓
              [ Note Storage or Upload ]
```

## Components

- **Jitsi Meet**: Video conferencing platform with multitrack recording
- **Prosody**: XMPP server with event sync for speaker identification
- **Parakeet ASR**: Fast streaming speech-to-text using Shadowfita's FastAPI implementation
- **Ollama**: Local LLM for clinical summarization
- **OpenEMR**: (Optional) Electronic Medical Records integration
- **Nginx Proxy Manager**: Reverse proxy for service management

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- NVIDIA GPU (optional, for faster ASR processing)
- At least 16GB RAM recommended
- 50GB free disk space for models and recordings

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/telehealth-transcription-pipeline.git
cd telehealth-transcription-pipeline
```

### 2. Configure Environment

Create a `.env` file:

```bash
# Environment Configuration
PROJECT=official              # official (for staging), empty for production
ENVIRONMENT=staging          # staging, production, dev, etc.
DOMAIN_BASE=localhost        # localhost, yourdomain.com, etc.

# Service URLs (auto-generated from above variables)
# For staging: official-staging-* containers
# For production: production-* containers (no PROJECT prefix)

# Telesalud Integration (Secure API-based approach)
TELESALUD_CONTAINER=${PROJECT:+${PROJECT}-}${ENVIRONMENT}-telehealth-web-1
TELESALUD_API_BASE_URL=http://${TELESALUD_CONTAINER}
TELESALUD_API_TOKEN=your-sanctum-api-token-here  # Required for secure data access
TELESALUD_API_URL=http://${TELESALUD_CONTAINER}/videoconsultation/evolution
TELESALUD_WEBHOOK_URL=http://${TELESALUD_CONTAINER}/api/webhook/evolution
USE_WEBHOOK=true  # true for new webhook endpoint, false for legacy form method
WEBHOOK_TOKEN=your-webhook-token-here  # Optional, for webhook security

# Service Container Names
PARAKEET_CONTAINER=${PROJECT:+${PROJECT}-}${ENVIRONMENT}-parakeet-asr-parakeet-asr
OLLAMA_CONTAINER=${PROJECT:+${PROJECT}-}${ENVIRONMENT}-ollama-llm
OPENEMR_CONTAINER=${PROJECT:+${PROJECT}-}${ENVIRONMENT}-openemr-1
JITSI_WEB_CONTAINER=jitsi-docker-web-1
PROSODY_CONTAINER=jitsi-docker-prosody-1

# OpenEMR Integration (optional)
OPENEMR_API_KEY=your-api-key-here

# GPU Configuration (remove for CPU-only)
CUDA_VISIBLE_DEVICES=0
```

### 3. Deploy the Pipeline Service

**Important**: All other services (Jitsi, Prosody, Parakeet, Ollama, etc.) are assumed to be already running on the `frontend-official-staging` network.

```bash
# Deploy ONLY the pipeline service
docker-compose -f docker-compose.pipeline.yml up -d

# Check pipeline service status
docker-compose -f docker-compose.pipeline.yml ps

# View pipeline logs
docker-compose -f docker-compose.pipeline.yml logs -f
```

If you need to initialize the Ollama model:
```bash
# Run this on the existing Ollama container
docker exec official-staging-ollama-llm ollama pull gpt-oss:20b
```

### 4. Configure Telesalud Webhooks

In your telesalud module, configure the webhook notification URL:

```bash
# In telesalud .env file (add alongside existing NOTIFICATION_URL for OpenEMR)
TRANSCRIPTION_NOTIFICATION_URL=http://${PROJECT:+${PROJECT}-}${ENVIRONMENT}-transcription-pipeline:9090/webhook/telesalud
TRANSCRIPTION_NOTIFICATION_TOKEN=your-webhook-token-here  # Optional, same as pipeline WEBHOOK_TOKEN

# Keep your existing OpenEMR notification
NOTIFICATION_URL=your-existing-openemr-webhook-url
NOTIFICATION_TOKEN=your-existing-openemr-token
```

### 5. Configure Nginx Proxy Manager

Access NPM at `http://localhost:81` (default: admin@example.com / changeme)

Add proxy hosts (using your naming convention):
- Jitsi Meet: `vcbknd-${ENVIRONMENT}.${DOMAIN_BASE}` → `http://jitsi-docker-web-1:80`
- Parakeet API: `asr-${ENVIRONMENT}.${DOMAIN_BASE}` → `http://${PARAKEET_CONTAINER}:8000`
- Ollama LLM: `llm-${ENVIRONMENT}.${DOMAIN_BASE}` → `http://${OLLAMA_CONTAINER}:11434`
- Telesalud: `vc-${ENVIRONMENT}.${DOMAIN_BASE}` → `http://${TELESALUD_CONTAINER}:80`
- OpenEMR: `${ENVIRONMENT}-notes.${DOMAIN_BASE}` → `http://${OPENEMR_CONTAINER}:80`
- Pipeline Webhook: `webhook-${ENVIRONMENT}.${DOMAIN_BASE}` → `http://${PROJECT:+${PROJECT}-}${ENVIRONMENT}-transcription-pipeline:9090`

**Example for staging environment:**
- Jitsi Meet: `vcbknd-staging.localhost` → `http://jitsi-docker-web-1:80`
- Parakeet API: `asr-staging.localhost` → `http://official-staging-parakeet-asr-parakeet-asr:8000`
- Ollama LLM: `llm-staging.localhost` → `http://official-staging-ollama-llm:11434`
- Telesalud: `vc-staging.localhost` → `http://official-staging-telehealth-web-1:80`
- OpenEMR: `staging-notes.localhost` → `http://official-staging-openemr-1:80`
- Pipeline Webhook: `webhook-staging.localhost` → `http://official-staging-transcription-pipeline:9090`

## Usage

### Recording a Telehealth Session

1. Start a Jitsi Meet conference
2. Enable multitrack recording in the meeting
3. Conduct the telehealth consultation
4. Stop recording when finished

### Processing Recordings

The pipeline automatically processes recordings when they're finalized:

```bash
# Manual processing (if needed)
docker-compose -f docker-compose.pipeline.yml run pipeline /pipeline/finalize.sh /recordings/meeting-id/

# View logs
docker-compose -f docker-compose.pipeline.yml logs -f pipeline
```

### Output Files

For each recording, the pipeline generates:

- `speaker1.wav`, `speaker2.wav` - Individual audio tracks
- `speaker1_transcript.json` - Individual transcriptions
- `speaker_mapping.json` - Speaker identification mapping
- `final_merged.json` - Combined transcript with speaker labels
- `transcript.txt` - Human-readable transcript
- `clinical_summary.json` - LLM-generated summary
- `final_note.txt` - Clinical note ready for EMR
- `telesalud_upload.json` - Confirmation of evolution field update

### Secure Integration Flow

1. **Consultation Events**: Telesalud sends minimal webhook notifications (no patient data)
2. **Recording**: Jitsi records multitrack audio during consultation  
3. **Event Notification**: Telesalud sends `videoconsultation-finished` webhook with only consultation ID
4. **Secure Data Retrieval**: Pipeline makes authenticated API call to get patient/provider data
5. **Processing**: Pipeline processes recording with full consultation context
6. **Summary Upload**: AI-generated summary sent back to telesalud evolution field

**Security Benefits:**
- ✅ Patient data only transmitted when needed with proper authentication
- ✅ Audit trail of all data access via API logs
- ✅ Principle of least privilege - minimal data in webhooks
- ✅ Sanctum token-based authentication for all patient data access

## Pipeline Scripts

### finalize.sh
Main orchestration script that:
- Converts .mka files to .wav
- Sends audio to Parakeet ASR
- Maps speakers using Prosody events
- Merges transcripts
- Generates clinical summary

### send_to_parakeet.py
- Connects to Parakeet WebSocket API
- Streams audio for real-time transcription
- Saves transcripts as JSON

### map_endpoints.py
- Reads Prosody event logs
- Maps Jitsi endpoints to participant names
- Creates speaker identification mapping

### merge_transcripts.py
- Combines individual transcripts
- Applies speaker mapping
- Generates unified transcript

### summarize_with_ollama.py
- Sends transcript to Ollama LLM
- Generates structured clinical summary
- Formats output for EMR integration

### send_to_telesalud.py
- Sends clinical notes to telesalud evolution field
- Uses consultation metadata for patient/provider context
- Handles medic authentication with consultation secrets

### send_to_openemr.py
- Uploads clinical notes to OpenEMR (optional)
- Handles authentication
- Provides fallback to shared directory

### telesalud_api_client.py
- Securely retrieves consultation data via authenticated API calls
- Uses Sanctum token authentication for patient data access
- Stores consultation metadata for pipeline processing

### webhook_handler.py
- Receives minimal telesalud event notifications (no patient data)
- Stores event data for pipeline processing
- Provides API endpoints for webhook status and consultation lists

## Configuration

### Parakeet ASR Settings

Configure in `docker-compose.yml`:
```yaml
environment:
  - MODEL_PATH=/models/parakeet-tdt-0.6b-v2
  - CUDA_VISIBLE_DEVICES=0  # GPU selection
```

### Ollama Model Selection

```yaml
environment:
  - OLLAMA_MODEL=gpt-oss:20b  # Can use other models
```

### Recording Directory Structure

```
/recordings/
  └── meeting-12345/
      ├── speaker1.mka
      ├── speaker2.mka
      └── metadata.json
```

## Troubleshooting

### Check Service Logs
```bash
docker-compose logs parakeet-asr
docker-compose logs ollama
docker-compose logs pipeline
```

### Common Issues

1. **Parakeet WebSocket Connection Failed**
   - Check if Parakeet service is running
   - Verify PARAKEET_WS_URL environment variable

2. **Ollama Model Not Found**
   - Run `docker-compose run model-init`
   - Check available models: `docker exec ollama ollama list`

3. **No Audio in Recordings**
   - Verify Jitsi multitrack recorder configuration
   - Check recording permissions in browser

4. **GPU Not Detected**
   - Install NVIDIA Container Toolkit
   - Verify with: `docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi`

## Development

### Running Pipeline Components Individually

```bash
# Test ASR
python pipeline/send_to_parakeet.py /path/to/audio.wav

# Test speaker mapping
python pipeline/map_endpoints.py /logs/meeting.json

# Test transcript merge
python pipeline/merge_transcripts.py /recordings/meeting-id/

# Test summarization
python pipeline/summarize_with_ollama.py /recordings/meeting-id/final_merged.json
```

### Adding Custom Models

1. For Parakeet: Mount model directory in docker-compose.yml
2. For Ollama: `docker exec ollama ollama pull model-name`

## Security Considerations

- Use HTTPS for all external endpoints
- Secure API keys in environment variables
- Implement access controls in NPM
- Encrypt recordings at rest
- Follow HIPAA compliance guidelines

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the MIT License - see LICENSE file for details.

## Acknowledgments

- [Jitsi Meet](https://github.com/jitsi/jitsi-meet)
- [Parakeet FastAPI](https://github.com/Shadowfita/parakeet-tdt-0.6b-v2-fastapi)
- [Ollama](https://github.com/jmorganca/ollama)
- [OpenEMR](https://github.com/openemr/openemr)