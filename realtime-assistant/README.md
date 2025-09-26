# Real-Time Clinical Assistant

🎯 **Live clinical guidance during telehealth consultations using AI-powered conversation analysis**

## Overview

The Real-Time Clinical Assistant provides **live question suggestions** and **clinical guidance** during telehealth consultations by:

1. **Audio Analysis**: Connects to existing Parakeet ASR for real-time patient speech transcription
2. **Clinical Intelligence**: Uses telesalud's Ollama endpoints for consultation-specific analysis  
3. **Live Suggestions**: Provides popup question suggestions to providers during consultations
4. **Context Awareness**: Maintains conversation state and evaluation progress

## Architecture

```
Telesalud Recording → Real-Time Assistant → Parakeet ASR → Transcription
                                ↓
Consultation Context ← Clinical Analysis ← Ollama Endpoints
                                ↓
Provider Interface ← Question Suggestions ← WebSocket Notifications
```

## Key Features

### 🔄 **Real-Time Processing**
- Leverages Parakeet's built-in WebSocket streaming and VAD
- No additional audio processing overhead
- Live transcription with confidence scoring

### 🧠 **Clinical Intelligence**
- **Autism Assessment**: ADOS-2/ADI-R guided question suggestions
- **ADHD Evaluation**: DSM-5 criteria-based guidance
- **General Medical**: Symptom-driven interview assistance
- Context-aware conversation tracking

### 📱 **Seamless Integration**
- Uses telesalud's existing recording button infrastructure
- WebSocket-based popup notifications
- No disruption to existing consultation workflow

## Consultation Types Supported

| Type | Ollama Endpoint | Features |
|------|----------------|----------|
| Autism | `/api/ollama/autism-assessment` | ADOS-2 guidance, sensory processing, social communication |
| ADHD | `/api/ollama/adhd-evaluation` | DSM-5 criteria, functional impairment assessment |
| General | `/api/ollama/general-medical` | Symptom assessment, differential diagnosis |

## WebSocket Protocol

### **Start Session**
```json
{
  "type": "start_session",
  "consultation_id": "consultation-123",
  "consultation_type": "autism"
}
```

### **Audio Streaming**
```
Binary audio data (16kHz mono PCM) → Forwarded to Parakeet
```

### **Clinical Suggestions** (Received)
```json
{
  "type": "clinical_suggestion",
  "consultation_id": "consultation-123",
  "suggestions": {
    "next_questions": [
      "Can you tell me more about how they interact with other children?",
      "Have you noticed any repetitive behaviors or routines?"
    ],
    "observed_indicators": ["social_communication_differences"],
    "priority": "high"
  }
}
```

## Deployment

### **Prerequisites**
- Parakeet ASR container running (`official-staging-parakeet-asr-parakeet-asr`)
- Telesalud with Ollama endpoints (`official-staging-telehealth-web-1`)
- Telesalud API token for secure authentication

### **Environment Configuration**
```bash
# Copy and customize environment
cp .env.example .env

# Required variables
TELESALUD_API_TOKEN=your-sanctum-token-here
PARAKEET_CONTAINER=official-staging-parakeet-asr-parakeet-asr
TELESALUD_CONTAINER=official-staging-telehealth-web-1
```

### **Deploy Real-Time Assistant**
```bash
# Deploy only the real-time assistant (other services already running)
docker-compose -f docker-compose.realtime.yml up -d

# Check status
docker-compose -f docker-compose.realtime.yml ps
docker-compose -f docker-compose.realtime.yml logs -f realtime-assistant
```

## Integration with Telesalud

### **Frontend Integration** (JavaScript)
```javascript
class ClinicalAssistant {
    constructor(consultationId, consultationType) {
        this.ws = new WebSocket('ws://realtime-assistant:9091');
        this.consultationId = consultationId;
        this.consultationType = consultationType;
    }
    
    async startSession() {
        // Start clinical assistant session
        this.ws.send(JSON.stringify({
            type: 'start_session',
            consultation_id: this.consultationId,
            consultation_type: this.consultationType
        }));
        
        // Start audio capture from existing recording button
        this.setupAudioForwarding();
    }
    
    setupAudioForwarding() {
        // Use existing telesalud recording infrastructure
        navigator.mediaDevices.getUserMedia({audio: true})
            .then(stream => {
                // Forward patient audio to real-time assistant
                this.forwardAudioToAssistant(stream);
            });
    }
    
    onSuggestion(suggestion) {
        // Display popup with clinical suggestions
        this.showClinicalGuidancePopup(suggestion);
    }
}
```

### **Backend Integration** (Laravel)
```php
// Telesalud OllamaController methods already implemented:
// - autismAssessment()
// - adhdEvaluation() 
// - generalMedical()
```

## Monitoring

### **Health Checks**
```bash
# Check real-time assistant health
curl http://localhost:9091/health

# View active sessions
curl http://localhost:9091/sessions
```

### **Logs**
```bash
# Real-time processing logs
docker-compose -f docker-compose.realtime.yml logs -f realtime-assistant

# Audio forwarding status
docker logs official-staging-parakeet-asr-parakeet-asr
```

## Development

### **Testing Audio Pipeline**
```bash
# Test Parakeet connectivity
python -c "
import asyncio, websockets
async def test():
    async with websockets.connect('ws://localhost:8000/ws') as ws:
        print('Connected to Parakeet')
asyncio.run(test())
"
```

### **Testing Clinical Analysis**
```bash
# Test Ollama endpoint
curl -X POST http://localhost/api/ollama/autism-assessment \
  -H "Authorization: Bearer $TELESALUD_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_statement": "My child doesn'\''t make eye contact much",
    "consultation_type": "autism"
  }'
```

## Performance

### **Latency Targets**
- **Audio → Transcription**: <500ms (Parakeet WebSocket)
- **Transcription → Analysis**: <2s (Ollama processing)
- **Analysis → Suggestion**: <100ms (WebSocket delivery)
- **Total end-to-end**: <3s

### **Resource Usage**
- **CPU**: Low (audio forwarding only)
- **Memory**: ~500MB (conversation state)
- **Network**: WebSocket connections to Parakeet + telesalud

## Security

### **Data Handling**
- ✅ Audio forwarded directly to Parakeet (no storage)
- ✅ Conversation state in memory only
- ✅ Authenticated API calls to telesalud
- ✅ No persistent PHI storage

### **Network Security**
- All communication within `frontend-official-staging` network
- API authentication via Sanctum tokens
- WebSocket connections from telesalud only

## Troubleshooting

### **Common Issues**

1. **No Transcriptions Received**
   - Check Parakeet container status
   - Verify WebSocket URL: `ws://parakeet-asr:8000/ws`
   - Ensure audio format: 16kHz mono PCM

2. **No Clinical Suggestions**
   - Verify telesalud API token
   - Check Ollama endpoint availability
   - Review consultation type mapping

3. **WebSocket Disconnections**
   - Check network connectivity
   - Verify consultation session state
   - Review connection timeout settings

This real-time assistant transforms your existing infrastructure into an intelligent clinical guidance system! 🚀