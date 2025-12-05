# Pipeline Integration Modes

The Telehealth Transcription Pipeline supports **three integration modes** for processing recordings, providing flexibility based on your infrastructure and workflow needs.

## Available Modes

### 1. **Jitsi Mode** (`INTEGRATION_MODE=jitsi`)
Direct integration with Jitsi's multitrack recorder using the finalize script capability.

**How it works:**
- Jitsi automatically calls `/pipeline/finalize_wrapper.sh` when recording completes
- No external triggers needed
- Immediate processing with minimal latency
- Recording directory passed directly from Jitsi

**Configuration:**
```yaml
# docker-compose.jitsi-integrated.yml
multitrack-recorder:
  environment:
    - FINALIZE_SCRIPT_PATH=/pipeline/finalize_wrapper.sh
    - FINALIZE_SCRIPT_ENABLED=true
  volumes:
    - ./pipeline:/pipeline:ro
```

**Pros:**
- ✅ Fully automatic
- ✅ No network dependencies
- ✅ Minimal latency
- ✅ Simple architecture

**Cons:**
- ❌ Tightly coupled to Jitsi
- ❌ Requires Jitsi configuration access
- ❌ Less flexible for external triggers

### 2. **Webhook Mode** (`INTEGRATION_MODE=webhook`)
Event-driven processing triggered by telesalud webhooks.

**How it works:**
- Telesalud sends webhook when consultation finishes
- Webhook handler triggers pipeline processing
- Consultation metadata retrieved via API
- Processing happens asynchronously

**Configuration:**
```bash
# .env
INTEGRATION_MODE=webhook
WEBHOOK_TOKEN=your-secure-token
WEBHOOK_PORT=9090
```

**Webhook endpoint:** `http://pipeline:9090/webhook/telesalud`

**Pros:**
- ✅ Decoupled from Jitsi
- ✅ External system integration
- ✅ Consultation context available
- ✅ Audit trail via webhooks

**Cons:**
- ❌ Network dependency
- ❌ Potential delays
- ❌ Requires webhook configuration

### 3. **Dual Mode** (`INTEGRATION_MODE=dual`) - **Recommended**
Supports both Jitsi automatic and webhook triggers simultaneously.

**How it works:**
- Jitsi can trigger directly when recording completes
- Webhooks can also trigger processing
- Duplicate processing prevented via status tracking
- Maximum flexibility and reliability

**Configuration:**
```bash
# .env
INTEGRATION_MODE=dual  # Default
```

**Pros:**
- ✅ Best of both worlds
- ✅ Fallback options
- ✅ Maximum flexibility
- ✅ Development/testing friendly

**Cons:**
- ❌ Slightly more complex
- ❌ Need to prevent duplicate processing

## Deployment Examples

### Example 1: Pure Jitsi Integration
```bash
# Use the integrated compose file
docker-compose -f docker-compose.jitsi-integrated.yml up -d

# Set environment
echo "INTEGRATION_MODE=jitsi" >> .env
```

### Example 2: Webhook-Only Mode
```bash
# Use standard pipeline compose
docker-compose -f docker-compose.pipeline.yml up -d

# Configure webhook mode
echo "INTEGRATION_MODE=webhook" >> .env

# Configure telesalud to send webhooks to:
# http://pipeline:9090/webhook/telesalud
```

### Example 3: Dual Mode (Recommended)
```bash
# Deploy both configurations
docker-compose -f docker-compose.jitsi-integrated.yml up -d

# Default mode is dual
echo "INTEGRATION_MODE=dual" >> .env
```

## Processing Flow Comparison

### Jitsi Mode Flow
```
Recording Ends → Jitsi → finalize_wrapper.sh → Pipeline Processing
```

### Webhook Mode Flow
```
Consultation Ends → Telesalud Webhook → webhook_handler.py → finalize_wrapper.sh → Pipeline Processing
```

### Dual Mode Flow
```
Recording Ends ────→ Jitsi ─────────────┐
                                         ├→ finalize_wrapper.sh → Pipeline
Consultation Ends → Telesalud Webhook ──┘
```

## Status Tracking

All modes update status in `/shared/consultations/{consultation_id}_processing.json`:

```json
{
  "consultation_id": "consultation-123",
  "recording_dir": "/recordings/consultation-123",
  "trigger_source": "jitsi|webhook",
  "processing_started": "2024-01-15T10:00:00Z",
  "processing_completed": "2024-01-15T10:02:00Z",
  "status": "completed",
  "exit_code": 0
}
```

## Manual Processing

Regardless of mode, you can always manually trigger processing:

```bash
# Direct execution
docker exec pipeline /pipeline/finalize_wrapper.sh /recordings/meeting-123 manual

# Via docker-compose run
docker-compose -f docker-compose.pipeline.yml run pipeline \
  /pipeline/finalize_wrapper.sh /recordings/meeting-123 manual
```

## Monitoring

### Check Integration Mode
```bash
docker exec pipeline env | grep INTEGRATION_MODE
```

### View Processing Status
```bash
# List all processed consultations
ls -la /shared/consultations/*_processing.json

# Check specific consultation
cat /shared/consultations/consultation-123_processing.json
```

### Monitor Webhook Handler
```bash
# Health check
curl http://localhost:9090/webhook/health

# List consultations
curl http://localhost:9090/webhook/consultations
```

## Troubleshooting

### Jitsi Mode Not Triggering
1. Check `FINALIZE_SCRIPT_PATH` in multitrack recorder config
2. Verify script has execute permissions: `chmod +x /pipeline/finalize_wrapper.sh`
3. Check recorder logs: `docker logs jitsi-docker_multitrack_recorder`

### Webhook Mode Not Triggering
1. Verify webhook URL in telesalud configuration
2. Check webhook token matches
3. Monitor webhook handler logs: `docker logs pipeline | grep WEBHOOK`
4. Test webhook manually:
   ```bash
   curl -X POST http://localhost:9090/webhook/telesalud \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer your-token" \
     -d '{"vc":{"secret":"test-123","status":"finished"},"topic":"videoconsultation-finished"}'
   ```

### Duplicate Processing
In dual mode, the wrapper script prevents duplicate processing by checking the processing status file. If a consultation is already being processed, subsequent triggers are ignored.

## Recommendations

1. **Production**: Use `dual` mode for maximum reliability
2. **Development**: Use `webhook` mode for easier testing
3. **Simple Deployments**: Use `jitsi` mode if you control Jitsi configuration
4. **Complex Integrations**: Use `webhook` mode for external system coordination

## Migration Guide

### From Webhook-Only to Dual Mode

1. Update `.env`:
   ```bash
   INTEGRATION_MODE=dual
   ```

2. Deploy integrated recorder:
   ```bash
   docker-compose -f docker-compose.jitsi-integrated.yml up -d
   ```

3. Mount pipeline scripts in recorder:
   ```yaml
   volumes:
     - ./pipeline:/pipeline:ro
   ```

4. Restart services:
   ```bash
   docker-compose restart
   ```

Both trigger methods will now work simultaneously!