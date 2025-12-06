# AI Processing Architecture

This document describes the AI-powered clinical documentation system for telesalud telehealth consultations.

## Overview

The system has **two separate AI processing paths**:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│                          TELESALUD PLATFORM                                 │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    DURING CONSULTATION                               │   │
│  │                    (Real-time Assistant)                             │   │
│  │                                                                      │   │
│  │   Doctor types notes ──▶ OllamaController.php ──▶ Ollama LLM        │   │
│  │                              │                         │             │   │
│  │                              │                         ▼             │   │
│  │                              │              "Suggest next question"  │   │
│  │                              │                         │             │   │
│  │                              ▼                         ▼             │   │
│  │                    Specialty Endpoints:        Real-time suggestions │   │
│  │                    - autismAssessment()        displayed to doctor   │   │
│  │                    - adhdEvaluation()                                │   │
│  │                    - generalMedical()                                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    AFTER CONSULTATION                                │   │
│  │                    (Post-processing Pipeline)                        │   │
│  │                                                                      │   │
│  │   Recording stops ──▶ Transcription Pipeline ──▶ Ollama LLM         │   │
│  │                              │                         │             │   │
│  │                              │                         ▼             │   │
│  │                              │              "Create clinical summary"│   │
│  │                              │                         │             │   │
│  │                              ▼                         ▼             │   │
│  │                    Customizable Prompts:       AI Notes section      │   │
│  │                    - default.txt               in evolution form     │   │
│  │                    - psychiatry.txt                                  │   │
│  │                    - pediatrics.txt                                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. Real-time Assistant (During Consultation)

### Purpose
Provide live AI suggestions to doctors during evaluations, helping them ask the right questions based on DSM-5 diagnostic criteria.

### Location
`telesalud/app/Http/Controllers/OllamaController.php`

### Endpoints

| Endpoint | Specialty | Persona |
|----------|-----------|---------|
| `/api/ollama/autism` | Autism Spectrum Disorder | Dr. Sarah Chen - Pediatric Developmental Specialist |
| `/api/ollama/adhd` | ADHD | Dr. Michael Rodriguez - Pediatric Neuropsychologist |
| `/api/ollama/general` | General Medical | Clinical Documentation AI |

### Flow

```
┌──────────────┐     ┌─────────────────────┐     ┌─────────────┐
│   Doctor     │────▶│  OllamaController   │────▶│   Ollama    │
│  types notes │     │  (specialty prompt) │     │    LLM      │
└──────────────┘     └─────────────────────┘     └──────┬──────┘
                                                        │
                                                        ▼
                     ┌─────────────────────┐     ┌─────────────┐
                     │  Suggested question │◀────│   Response  │
                     │  displayed in UI    │     │   (JSON)    │
                     └─────────────────────┘     └─────────────┘
```

### Example: Autism Assessment Prompt

```
You are Dr. Sarah Chen, a board-certified pediatric developmental specialist 
with 15 years of experience conducting autism spectrum disorder evaluations.

DSM-5 CRITERIA TO TRACK:
A. Social communication/interaction deficits:
   A1: Social-emotional reciprocity
   A2: Nonverbal communicative behaviors  
   A3: Developing/maintaining relationships

B. Restricted, repetitive patterns:
   B1: Stereotyped/repetitive motor movements or speech
   B2: Insistence on sameness, routines
   B3: Restricted, fixated interests
   B4: Hyper/hyporeactivity to sensory input

RESPONSE FORMAT: JSON
{
  "next_question": "specific question to ask",
  "targets_criteria": ["A1", "A2", etc.],
  "rationale": "why this question is important"
}
```

---

## 2. Post-consultation Summarization (After Recording)

### Purpose
Generate a structured clinical summary from the recorded consultation, with proper speaker diarization (who said what).

### Location
`telehealth-transcription-pipeline/pipeline/summarize_with_ollama.py`

### Prompt Templates
`telehealth-transcription-pipeline/pipeline/prompts/`

### Flow

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│  Multitrack     │────▶│   finalize.sh    │────▶│  speaker_mapping    │
│  Recording      │     │  Extract tracks  │     │  .json              │
│  (MKA file)     │     └──────────────────┘     └─────────────────────┘
└─────────────────┘              │                         │
                                 ▼                         │
                    ┌──────────────────────┐               │
                    │  Parakeet ASR        │               │
                    │  (per-speaker        │               │
                    │   transcription)     │               │
                    └──────────────────────┘               │
                                 │                         │
                                 ▼                         ▼
                    ┌──────────────────────────────────────────┐
                    │         merge_transcripts.py             │
                    │  Combine transcripts with speaker labels │
                    │  "Dr. Smith: How are you feeling?"       │
                    │  "Patient: I've been having headaches"   │
                    └──────────────────────────────────────────┘
                                          │
                                          ▼
                    ┌──────────────────────────────────────────┐
                    │       summarize_with_ollama.py           │
                    │                                          │
                    │  1. Load prompt template (default.txt)   │
                    │  2. Insert transcript + doctor notes     │
                    │  3. Call Ollama API                      │
                    │  4. Save clinical summary                │
                    └──────────────────────────────────────────┘
                                          │
                                          ▼
                    ┌──────────────────────────────────────────┐
                    │         send_to_telesalud.py             │
                    │  POST /api/webhook/evolution             │
                    │  → Updates AI Notes section              │
                    └──────────────────────────────────────────┘
```

---

## 3. Prompt Templates

### Directory Structure

```
/pipeline/prompts/
├── default.txt       # General medical consultation
├── psychiatry.txt    # Mental health (DSM-5 focused)
├── pediatrics.txt    # Child-focused
└── [specialty].txt   # Add more as needed
```

### Template Variables

| Variable | Description |
|----------|-------------|
| `{medic_name}` | Doctor's name |
| `{patient_name}` | Patient's name |
| `{conversation_text}` | Diarized transcript with speaker labels |
| `{doctor_notes}` | Doctor's typed notes (if any) |

### Default Template

```
You are a medical assistant helping to summarize a telehealth consultation 
between {medic_name} and {patient_name}.

Please provide a structured clinical summary combining the audio conversation 
transcript and the doctor's typed notes.

Include sections for:
1. Chief Complaint
2. History of Present Illness
3. Review of Systems (if mentioned)
4. Assessment
5. Plan/Recommendations
6. Follow-up (if discussed)

Keep the summary professional, concise, and clinically relevant.

Audio Conversation Transcript:
{conversation_text}

Doctor's Typed Notes:
{doctor_notes}

Clinical Summary:
```

### Psychiatry Template

```
You are a psychiatric medical assistant helping to summarize a telehealth 
mental health consultation between {medic_name} and {patient_name}.

Include sections for:
1. Chief Complaint / Presenting Problem
2. History of Present Illness
3. Mental Status Examination
4. DSM-5 Diagnostic Considerations
5. Risk Assessment (if applicable)
6. Treatment Plan
7. Follow-up

Audio Conversation Transcript:
{conversation_text}

Doctor's Typed Notes:
{doctor_notes}

Psychiatric Clinical Summary:
```

### Pediatrics Template

```
You are a pediatric medical assistant helping to summarize a telehealth 
consultation between {medic_name} and the patient {patient_name} 
(and their parent/guardian).

Include sections for:
1. Chief Complaint
2. History of Present Illness
3. Developmental Assessment (if discussed)
4. Review of Systems (pediatric-focused)
5. Growth and Nutrition (if mentioned)
6. Assessment
7. Plan/Recommendations
8. Follow-up

Audio Conversation Transcript:
{conversation_text}

Doctor's Typed Notes:
{doctor_notes}

Pediatric Clinical Summary:
```

---

## 4. Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_API_URL` | `http://ollama:11434/api/generate` | Ollama API endpoint |
| `OLLAMA_MODEL` | `llama3.2:3b` | Model to use for summarization |
| `PROMPTS_DIR` | `/pipeline/prompts` | Directory containing prompt templates |
| `DEFAULT_PROMPT_TYPE` | `default` | Default prompt template to use |

### Selecting a Prompt Template

**Option 1: Environment Variable (Global)**
```bash
DEFAULT_PROMPT_TYPE=psychiatry
```

**Option 2: Per-Consultation (via metadata)**
Include in consultation metadata:
```json
{
  "specialty": "psychiatry"
}
```
or
```json
{
  "prompt_type": "psychiatry"
}
```

---

## 5. Adding a New Specialty

1. Create a new file: `/pipeline/prompts/cardiology.txt`

2. Use the template variables:
```
You are a cardiology assistant helping to summarize a telehealth 
consultation between {medic_name} and {patient_name}.

Include sections for:
1. Chief Complaint
2. Cardiac History
3. Current Medications
4. Vital Signs (if mentioned)
5. Cardiovascular Examination Findings
6. ECG/Imaging Results (if discussed)
7. Assessment
8. Plan/Recommendations

Audio Conversation Transcript:
{conversation_text}

Doctor's Typed Notes:
{doctor_notes}

Cardiology Clinical Summary:
```

3. Set the prompt type via environment or metadata

---

## 6. Output Format

### Clinical Summary JSON
```json
{
  "recording_id": "abc123",
  "model": "llama3.2:3b",
  "summary": "Clinical summary text...",
  "metadata": {
    "total_speakers": 2,
    "total_segments": 45,
    "patient_name": "John Doe",
    "medic_name": "Dr. Smith",
    "doctor_notes_included": true,
    "sources": ["audio_transcript", "doctor_notes"]
  }
}
```

### Final Note Text
```
Telehealth Consultation Summary
Patient: John Doe
Provider: Dr. Smith
Recording ID: abc123
==================================================

1. Chief Complaint
Patient presents with recurring headaches...

2. History of Present Illness
...

==================================================
Generated by: llama3.2:3b
Sources: Audio transcript + Doctor's typed notes
```

---

## 7. Comparison: Real-time vs Post-processing

| Aspect | Real-time Assistant | Post-processing |
|--------|---------------------|-----------------|
| **When** | During consultation | After recording stops |
| **Purpose** | Suggest next questions | Create clinical summary |
| **Input** | Doctor's typed notes | Full audio transcript |
| **Output** | Single suggestion | Complete clinical note |
| **Prompts** | Hardcoded in PHP | File-based templates |
| **Specialty** | Endpoint-based | Template-based |
| **Location** | telesalud | transcription-pipeline |
