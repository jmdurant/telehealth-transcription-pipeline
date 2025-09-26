#!/usr/bin/env python3
"""
Conversation State Management for Real-Time Clinical Assistant
Maintains context and evaluation progress for different consultation types
"""
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class ConsultationType(Enum):
    AUTISM = "autism"
    ADHD = "adhd"
    GENERAL = "general"
    DEPRESSION = "depression"
    ANXIETY = "anxiety"

@dataclass
class ConversationSegment:
    speaker: str
    text: str
    timestamp: datetime
    confidence: float = 0.0
    processed: bool = False
    indicators: List[str] = None
    
    def __post_init__(self):
        if self.indicators is None:
            self.indicators = []
    
    def to_dict(self) -> dict:
        return {
            "speaker": self.speaker,
            "text": self.text,
            "timestamp": self.timestamp.isoformat(),
            "confidence": self.confidence,
            "processed": self.processed,
            "indicators": self.indicators
        }

@dataclass
class EvaluationProgress:
    areas_assessed: Dict[str, bool]
    indicators_found: List[str]
    confidence_level: float
    next_focus_areas: List[str]
    questions_asked: int
    completion_percentage: float
    
    def to_dict(self) -> dict:
        return asdict(self)

class ConversationStateManager:
    def __init__(self, consultation_id: str, consultation_type: ConsultationType):
        self.consultation_id = consultation_id
        self.consultation_type = consultation_type
        self.conversation_segments: List[ConversationSegment] = []
        self.evaluation_progress = self.initialize_evaluation_progress()
        self.session_start_time = datetime.now()
        self.last_activity_time = datetime.now()
        self.context_window_size = 10  # Number of recent segments to include in context
        
        # Consultation-specific evaluation frameworks
        self.evaluation_frameworks = {
            ConsultationType.AUTISM: {
                "areas": [
                    "social_communication",
                    "restricted_repetitive_behaviors", 
                    "sensory_processing",
                    "developmental_history",
                    "adaptive_functioning",
                    "cognitive_assessment"
                ],
                "key_indicators": [
                    "eye_contact_differences",
                    "social_reciprocity_challenges",
                    "repetitive_behaviors",
                    "sensory_sensitivities",
                    "communication_differences",
                    "developmental_delays"
                ]
            },
            ConsultationType.ADHD: {
                "areas": [
                    "inattention_symptoms",
                    "hyperactivity_symptoms",
                    "impulsivity_symptoms",
                    "functional_impairment",
                    "developmental_history",
                    "comorbid_conditions"
                ],
                "key_indicators": [
                    "attention_difficulties",
                    "hyperactive_behaviors",
                    "impulsive_actions",
                    "executive_function_challenges",
                    "academic_challenges",
                    "social_difficulties"
                ]
            },
            ConsultationType.GENERAL: {
                "areas": [
                    "chief_complaint",
                    "history_present_illness",
                    "review_of_systems",
                    "medical_history",
                    "social_history",
                    "assessment_plan"
                ],
                "key_indicators": [
                    "symptom_onset",
                    "symptom_severity",
                    "functional_impact",
                    "risk_factors",
                    "protective_factors"
                ]
            }
        }
    
    def initialize_evaluation_progress(self) -> EvaluationProgress:
        """Initialize evaluation progress based on consultation type"""
        framework = self.evaluation_frameworks.get(self.consultation_type, 
                                                   self.evaluation_frameworks[ConsultationType.GENERAL])
        
        areas_assessed = {area: False for area in framework["areas"]}
        
        return EvaluationProgress(
            areas_assessed=areas_assessed,
            indicators_found=[],
            confidence_level=0.0,
            next_focus_areas=framework["areas"][:3],  # Start with first 3 areas
            questions_asked=0,
            completion_percentage=0.0
        )
    
    async def add_patient_statement(self, text: str, confidence: float = 0.0) -> ConversationSegment:
        """Add a new patient statement to the conversation"""
        segment = ConversationSegment(
            speaker="patient",
            text=text.strip(),
            timestamp=datetime.now(),
            confidence=confidence,
            processed=False
        )
        
        self.conversation_segments.append(segment)
        self.last_activity_time = datetime.now()
        
        logger.info(f"Added patient statement to consultation {self.consultation_id}: {text[:50]}...")
        
        return segment
    
    async def add_provider_statement(self, text: str) -> ConversationSegment:
        """Add a provider statement/question to the conversation"""
        segment = ConversationSegment(
            speaker="provider",
            text=text.strip(),
            timestamp=datetime.now(),
            confidence=1.0,  # Provider statements are always high confidence
            processed=True   # Provider statements don't need AI analysis
        )
        
        self.conversation_segments.append(segment)
        self.evaluation_progress.questions_asked += 1
        self.last_activity_time = datetime.now()
        
        logger.info(f"Added provider question to consultation {self.consultation_id}")
        
        return segment
    
    def get_recent_context(self, max_segments: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get recent conversation context for AI analysis"""
        if max_segments is None:
            max_segments = self.context_window_size
        
        recent_segments = self.conversation_segments[-max_segments:]
        return [segment.to_dict() for segment in recent_segments]
    
    def get_unprocessed_patient_statements(self) -> List[ConversationSegment]:
        """Get patient statements that haven't been processed yet"""
        return [
            segment for segment in self.conversation_segments 
            if segment.speaker == "patient" and not segment.processed
        ]
    
    def mark_segment_processed(self, segment: ConversationSegment, indicators: List[str] = None):
        """Mark a segment as processed and add any identified indicators"""
        segment.processed = True
        
        if indicators:
            segment.indicators.extend(indicators)
            self.evaluation_progress.indicators_found.extend(indicators)
        
        # Update completion percentage
        total_areas = len(self.evaluation_progress.areas_assessed)
        assessed_areas = sum(1 for assessed in self.evaluation_progress.areas_assessed.values() if assessed)
        self.evaluation_progress.completion_percentage = (assessed_areas / total_areas) * 100
    
    def update_evaluation_progress(self, area: str, indicators: List[str] = None):
        """Update evaluation progress for a specific area"""
        if area in self.evaluation_progress.areas_assessed:
            self.evaluation_progress.areas_assessed[area] = True
            
            if indicators:
                self.evaluation_progress.indicators_found.extend(indicators)
            
            # Remove from next focus areas if completed
            if area in self.evaluation_progress.next_focus_areas:
                self.evaluation_progress.next_focus_areas.remove(area)
                
            # Add next unassessed area if available
            unassessed_areas = [
                area for area, assessed in self.evaluation_progress.areas_assessed.items()
                if not assessed
            ]
            
            if unassessed_areas and len(self.evaluation_progress.next_focus_areas) < 3:
                next_area = unassessed_areas[0]
                if next_area not in self.evaluation_progress.next_focus_areas:
                    self.evaluation_progress.next_focus_areas.append(next_area)
    
    def get_context_for_ai_analysis(self) -> Dict[str, Any]:
        """Prepare context data for AI analysis"""
        return {
            "consultation_id": self.consultation_id,
            "consultation_type": self.consultation_type.value,
            "session_duration_minutes": (datetime.now() - self.session_start_time).total_seconds() / 60,
            "recent_conversation": self.get_recent_context(),
            "evaluation_progress": self.evaluation_progress.to_dict(),
            "unprocessed_statements": [
                segment.to_dict() for segment in self.get_unprocessed_patient_statements()
            ],
            "key_indicators_framework": self.evaluation_frameworks[self.consultation_type]["key_indicators"],
            "focus_areas": self.evaluation_progress.next_focus_areas
        }
    
    def get_session_summary(self) -> Dict[str, Any]:
        """Get summary of the current session"""
        total_segments = len(self.conversation_segments)
        patient_segments = len([s for s in self.conversation_segments if s.speaker == "patient"])
        provider_segments = len([s for s in self.conversation_segments if s.speaker == "provider"])
        
        return {
            "consultation_id": self.consultation_id,
            "consultation_type": self.consultation_type.value,
            "session_start": self.session_start_time.isoformat(),
            "last_activity": self.last_activity_time.isoformat(),
            "duration_minutes": (datetime.now() - self.session_start_time).total_seconds() / 60,
            "total_segments": total_segments,
            "patient_statements": patient_segments,
            "provider_questions": provider_segments,
            "evaluation_progress": self.evaluation_progress.to_dict(),
            "indicators_found": len(self.evaluation_progress.indicators_found),
            "completion_percentage": self.evaluation_progress.completion_percentage
        }
    
    def is_session_active(self, timeout_minutes: int = 30) -> bool:
        """Check if session is still active based on last activity"""
        timeout_threshold = datetime.now() - timedelta(minutes=timeout_minutes)
        return self.last_activity_time > timeout_threshold
    
    def export_conversation(self) -> Dict[str, Any]:
        """Export complete conversation for storage or analysis"""
        return {
            "conversation_metadata": self.get_session_summary(),
            "complete_conversation": [segment.to_dict() for segment in self.conversation_segments],
            "final_evaluation_state": self.evaluation_progress.to_dict()
        }

# Session manager to handle multiple active consultations
class SessionManager:
    def __init__(self):
        self.active_sessions: Dict[str, ConversationStateManager] = {}
        self.session_timeout_minutes = 60  # Auto-cleanup after 1 hour of inactivity
    
    async def create_session(self, consultation_id: str, consultation_type: str) -> ConversationStateManager:
        """Create a new conversation session"""
        try:
            consult_type = ConsultationType(consultation_type)
        except ValueError:
            consult_type = ConsultationType.GENERAL
            logger.warning(f"Unknown consultation type '{consultation_type}', defaulting to GENERAL")
        
        session = ConversationStateManager(consultation_id, consult_type)
        self.active_sessions[consultation_id] = session
        
        logger.info(f"Created new session for consultation {consultation_id} (type: {consult_type.value})")
        
        return session
    
    def get_session(self, consultation_id: str) -> Optional[ConversationStateManager]:
        """Get existing session by consultation ID"""
        return self.active_sessions.get(consultation_id)
    
    async def cleanup_inactive_sessions(self):
        """Remove inactive sessions to free memory"""
        inactive_sessions = [
            consultation_id for consultation_id, session in self.active_sessions.items()
            if not session.is_session_active(self.session_timeout_minutes)
        ]
        
        for consultation_id in inactive_sessions:
            logger.info(f"Cleaning up inactive session: {consultation_id}")
            del self.active_sessions[consultation_id]
        
        return len(inactive_sessions)
    
    def get_all_active_sessions(self) -> Dict[str, Dict[str, Any]]:
        """Get summary of all active sessions"""
        return {
            consultation_id: session.get_session_summary()
            for consultation_id, session in self.active_sessions.items()
        }

# Global session manager instance
session_manager = SessionManager()

# Periodic cleanup task
async def periodic_cleanup():
    """Periodic task to cleanup inactive sessions"""
    while True:
        try:
            cleaned_count = await session_manager.cleanup_inactive_sessions()
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} inactive sessions")
        except Exception as e:
            logger.error(f"Error during session cleanup: {e}")
        
        # Run cleanup every 10 minutes
        await asyncio.sleep(600)