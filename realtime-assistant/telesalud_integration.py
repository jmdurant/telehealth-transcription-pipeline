#!/usr/bin/env python3
"""
Telesalud Integration for Real-Time Clinical Assistant
Handles communication with telesalud's Ollama endpoints and WebSocket notifications
"""
import os
import json
import asyncio
import aiohttp
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from conversation_state import ConversationStateManager, ConsultationType

logger = logging.getLogger(__name__)

class TelesaludAPIClient:
    def __init__(self):
        self.base_url = os.environ.get("TELESALUD_API_BASE_URL", "http://official-staging-telehealth-web-1")
        self.api_token = os.environ.get("TELESALUD_API_TOKEN", "")
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_token}"
        }
        
        # Endpoint mapping for different consultation types
        self.ollama_endpoints = {
            ConsultationType.AUTISM: "/api/ollama/autism-assessment",
            ConsultationType.ADHD: "/api/ollama/adhd-evaluation", 
            ConsultationType.GENERAL: "/api/ollama/general-medical",
            ConsultationType.DEPRESSION: "/api/ollama/general-medical",  # Use general for now
            ConsultationType.ANXIETY: "/api/ollama/general-medical"      # Use general for now
        }
    
    async def analyze_patient_statement(self, session: ConversationStateManager, patient_statement: str) -> Optional[Dict[str, Any]]:
        """
        Send patient statement to telesalud Ollama endpoint for analysis
        
        Args:
            session: Current conversation session
            patient_statement: Latest patient statement to analyze
            
        Returns:
            Analysis results with question suggestions and indicators
        """
        try:
            endpoint = self.ollama_endpoints.get(session.consultation_type, 
                                               self.ollama_endpoints[ConsultationType.GENERAL])
            
            url = f"{self.base_url}{endpoint}"
            
            # Prepare request payload
            payload = {
                "consultation_id": session.consultation_id,
                "consultation_type": session.consultation_type.value,
                "patient_statement": patient_statement,
                "conversation_context": session.get_recent_context(max_segments=5),
                "evaluation_progress": session.evaluation_progress.to_dict(),
                "focus_areas": session.evaluation_progress.next_focus_areas,
                "session_duration_minutes": (datetime.now() - session.session_start_time).total_seconds() / 60,
                "questions_asked_count": session.evaluation_progress.questions_asked
            }
            
            logger.info(f"Sending analysis request to {url} for consultation {session.consultation_id}")
            
            async with aiohttp.ClientSession() as client_session:
                async with client_session.post(url, json=payload, headers=self.headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"Received analysis response for consultation {session.consultation_id}")
                        return result
                    else:
                        error_text = await response.text()
                        logger.error(f"API error {response.status}: {error_text}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error calling telesalud analysis API: {e}")
            return None
    
    async def get_consultation_metadata(self, consultation_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve consultation metadata from telesalud API
        
        Args:
            consultation_id: The consultation secret/ID
            
        Returns:
            Consultation metadata or None if error
        """
        try:
            url = f"{self.base_url}/api/videoconsultation/data"
            params = {"vc": consultation_id}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=self.headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data
                    else:
                        logger.error(f"Failed to get consultation metadata: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error getting consultation metadata: {e}")
            return None

class SuggestionFormatter:
    """Format AI analysis results into actionable suggestions for providers"""
    
    @staticmethod
    def format_autism_suggestions(analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Format autism assessment suggestions"""
        return {
            "type": "autism_assessment",
            "priority": analysis.get("priority", "medium"),
            "title": "Autism Assessment Guidance",
            "suggestions": {
                "next_questions": analysis.get("next_questions", []),
                "observed_indicators": analysis.get("autism_indicators", []),
                "areas_to_explore": analysis.get("focus_areas", []),
                "assessment_tools": analysis.get("recommended_tools", [])
            },
            "clinical_notes": analysis.get("clinical_observations", ""),
            "timestamp": datetime.now().isoformat()
        }
    
    @staticmethod
    def format_adhd_suggestions(analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Format ADHD evaluation suggestions"""
        return {
            "type": "adhd_evaluation", 
            "priority": analysis.get("priority", "medium"),
            "title": "ADHD Evaluation Guidance",
            "suggestions": {
                "next_questions": analysis.get("next_questions", []),
                "symptom_indicators": analysis.get("adhd_indicators", []),
                "functional_areas": analysis.get("functional_impairment", []),
                "rating_scales": analysis.get("recommended_scales", [])
            },
            "clinical_notes": analysis.get("clinical_observations", ""),
            "timestamp": datetime.now().isoformat()
        }
    
    @staticmethod
    def format_general_suggestions(analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Format general medical consultation suggestions"""
        return {
            "type": "general_medical",
            "priority": analysis.get("priority", "medium"),
            "title": "Clinical Assessment Guidance", 
            "suggestions": {
                "next_questions": analysis.get("next_questions", []),
                "clinical_indicators": analysis.get("indicators", []),
                "diagnostic_considerations": analysis.get("differential_diagnosis", []),
                "recommended_assessments": analysis.get("recommended_assessments", [])
            },
            "clinical_notes": analysis.get("clinical_observations", ""),
            "timestamp": datetime.now().isoformat()
        }
    
    @classmethod
    def format_suggestions(cls, session: ConversationStateManager, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Format suggestions based on consultation type"""
        if session.consultation_type == ConsultationType.AUTISM:
            return cls.format_autism_suggestions(analysis)
        elif session.consultation_type == ConsultationType.ADHD:
            return cls.format_adhd_suggestions(analysis)
        else:
            return cls.format_general_suggestions(analysis)

class ClinicalAssistantEngine:
    """Main engine for real-time clinical assistance"""
    
    def __init__(self):
        self.telesalud_client = TelesaludAPIClient()
        self.suggestion_formatter = SuggestionFormatter()
        self.processing_queue = asyncio.Queue()
        self.suggestion_callbacks = []  # WebSocket handlers to notify
        
    def add_suggestion_callback(self, callback):
        """Add callback function to receive suggestions"""
        self.suggestion_callbacks.append(callback)
    
    async def process_patient_statement(self, session: ConversationStateManager, statement: str) -> Optional[Dict[str, Any]]:
        """
        Process a patient statement and generate clinical suggestions
        
        Args:
            session: Current conversation session
            statement: Patient statement to analyze
            
        Returns:
            Formatted suggestions for the provider
        """
        try:
            # Add statement to session
            segment = await session.add_patient_statement(statement)
            
            # Get AI analysis from telesalud
            analysis = await self.telesalud_client.analyze_patient_statement(session, statement)
            
            if not analysis:
                logger.warning(f"No analysis received for consultation {session.consultation_id}")
                return None
            
            # Mark segment as processed and update session state
            indicators = analysis.get("indicators", [])
            session.mark_segment_processed(segment, indicators)
            
            # Update evaluation progress if specific areas were assessed
            for area in analysis.get("areas_assessed", []):
                session.update_evaluation_progress(area, indicators)
            
            # Format suggestions for provider
            formatted_suggestions = self.suggestion_formatter.format_suggestions(session, analysis)
            
            # Notify all registered callbacks (WebSocket connections)
            await self.notify_suggestion_callbacks(session.consultation_id, formatted_suggestions)
            
            logger.info(f"Generated suggestions for consultation {session.consultation_id}")
            
            return formatted_suggestions
            
        except Exception as e:
            logger.error(f"Error processing patient statement: {e}")
            return None
    
    async def notify_suggestion_callbacks(self, consultation_id: str, suggestions: Dict[str, Any]):
        """Notify all registered callbacks about new suggestions"""
        for callback in self.suggestion_callbacks:
            try:
                await callback(consultation_id, suggestions)
            except Exception as e:
                logger.error(f"Error in suggestion callback: {e}")
    
    async def start_processing_queue(self):
        """Start background processing of queued statements"""
        while True:
            try:
                # Wait for new items in the processing queue
                session, statement = await self.processing_queue.get()
                
                # Process the statement
                await self.process_patient_statement(session, statement)
                
                # Mark task as done
                self.processing_queue.task_done()
                
            except Exception as e:
                logger.error(f"Error in processing queue: {e}")
                await asyncio.sleep(1)  # Brief pause before continuing
    
    async def queue_patient_statement(self, session: ConversationStateManager, statement: str):
        """Queue a patient statement for processing"""
        await self.processing_queue.put((session, statement))
        logger.debug(f"Queued statement for processing: {statement[:50]}...")

# Global assistant engine instance
assistant_engine = ClinicalAssistantEngine()