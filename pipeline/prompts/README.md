# Prompt Templates

This directory contains customizable prompt templates for AI-powered clinical summarization.

## Available Templates

| File | Specialty | Description |
|------|-----------|-------------|
| `default.txt` | General | Standard medical consultation summary |
| `psychiatry.txt` | Mental Health | DSM-5 focused, includes MSE and risk assessment |
| `pediatrics.txt` | Pediatrics | Child-focused, includes developmental assessment |

## Template Variables

Use these placeholders in your templates:

| Variable | Description | Example |
|----------|-------------|---------|
| `{medic_name}` | Doctor's name | "Dr. Sarah Smith" |
| `{patient_name}` | Patient's name | "John Doe" |
| `{conversation_text}` | Diarized transcript | "Dr. Smith: How are you?\nPatient: I'm okay..." |
| `{doctor_notes}` | Doctor's typed notes | "Chief complaint: headaches x 2 weeks" |

## Adding a New Template

1. Create a new file: `[specialty].txt`
2. Include the template variables where needed
3. Structure the prompt for your specialty's documentation needs

Example:
```
You are a {specialty} assistant helping to summarize a telehealth 
consultation between {medic_name} and {patient_name}.

Include sections for:
1. [Specialty-specific sections]
2. ...

Audio Conversation Transcript:
{conversation_text}

Doctor's Typed Notes:
{doctor_notes}

Clinical Summary:
```

## Selecting a Template

### Global Default (Environment Variable)
```bash
DEFAULT_PROMPT_TYPE=psychiatry
```

### Per-Consultation (Metadata)
Include in consultation metadata:
```json
{
  "specialty": "psychiatry"
}
```

## Best Practices

1. **Be specific** - Include specialty-relevant sections
2. **Use professional language** - The output will be in medical records
3. **Include all variables** - Especially `{conversation_text}` and `{doctor_notes}`
4. **End with a prompt** - e.g., "Clinical Summary:" to guide the LLM
5. **Test thoroughly** - Different models may respond differently
