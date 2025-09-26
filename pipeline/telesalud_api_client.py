#!/usr/bin/env python3
"""
Secure API client for retrieving consultation data from telesalud
Uses proper authentication and only requests data when needed
"""
import os
import requests
import json
from datetime import datetime

class TelesaludAPIClient:
    def __init__(self):
        self.base_url = os.environ.get("TELESALUD_API_BASE_URL", "http://official-staging-telehealth-web-1")
        self.api_token = os.environ.get("TELESALUD_API_TOKEN", "")
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        if self.api_token:
            self.headers["Authorization"] = f"Bearer {self.api_token}"
        
    def get_consultation_data(self, consultation_id):
        """
        Securely retrieve full consultation data via authenticated API
        
        Args:
            consultation_id (str): The consultation secret/ID
            
        Returns:
            dict: Full consultation data or None if error
        """
        try:
            url = f"{self.base_url}/api/videoconsultation/data"
            params = {"vc": consultation_id}
            
            print(f"[🔐 API] Requesting consultation data for {consultation_id}")
            
            response = requests.get(url, params=params, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                print(f"[✅ API] Successfully retrieved consultation data")
                return data
                
            elif response.status_code == 401:
                print(f"[❌ API] Authentication failed - check TELESALUD_API_TOKEN")
                return None
                
            elif response.status_code == 404:
                print(f"[❌ API] Consultation not found: {consultation_id}")
                return None
                
            else:
                print(f"[❌ API] API error {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            print(f"[❌ API] Error calling telesalud API: {e}")
            return None
    
    def extract_metadata_from_api_response(self, api_data):
        """
        Extract relevant metadata from API response
        
        Args:
            api_data (dict): Response from telesalud API
            
        Returns:
            dict: Extracted metadata for pipeline processing
        """
        if not api_data:
            return None
            
        # Extract videoconsultation data
        vc_data = api_data.get('videoconsultation', {})
        
        metadata = {
            'consultation_id': vc_data.get('secret'),
            'medic_secret': vc_data.get('medic_secret'),
            'status': vc_data.get('status'),
            'patient_id': vc_data.get('patient_id'),
            'patient_name': vc_data.get('patient_name'),
            'patient_number': vc_data.get('patient_number'),
            'medic_name': vc_data.get('medic_name'),
            'appointment_date': vc_data.get('appointment_date'),
            'doctor_notes': vc_data.get('doctor_notes'),
            'evolution': vc_data.get('evolution'),
            'start_date': vc_data.get('start_date'),
            'finish_date': vc_data.get('finish_date'),
            'medic_attendance_date': vc_data.get('medic_attendance_date'),
            'patient_attendance_date': vc_data.get('patient_attendance_date'),
            'api_retrieved': datetime.now().isoformat(),
            'recording_processed': False
        }
        
        return metadata
    
    def save_consultation_metadata(self, consultation_id, metadata):
        """
        Save consultation metadata to shared storage
        
        Args:
            consultation_id (str): Consultation ID
            metadata (dict): Metadata to save
        """
        metadata_dir = os.environ.get("METADATA_DIR", "/shared/consultations")
        os.makedirs(metadata_dir, exist_ok=True)
        
        filename = f"{consultation_id}_metadata.json"
        filepath = os.path.join(metadata_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"[💾] Saved consultation metadata to {filepath}")

def get_consultation_data_securely(consultation_id):
    """
    Main function to securely retrieve and save consultation data
    
    Args:
        consultation_id (str): Consultation secret/ID
        
    Returns:
        dict: Consultation metadata or None if error
    """
    client = TelesaludAPIClient()
    
    # Make authenticated API call
    api_data = client.get_consultation_data(consultation_id)
    if not api_data:
        return None
    
    # Extract metadata
    metadata = client.extract_metadata_from_api_response(api_data)
    if not metadata:
        return None
    
    # Save for pipeline processing
    client.save_consultation_metadata(consultation_id, metadata)
    
    return metadata

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: telesalud_api_client.py <consultation_id>")
        sys.exit(1)
    
    consultation_id = sys.argv[1]
    metadata = get_consultation_data_securely(consultation_id)
    
    if metadata:
        print(json.dumps(metadata, indent=2))
    else:
        print("Failed to retrieve consultation data")
        sys.exit(1)