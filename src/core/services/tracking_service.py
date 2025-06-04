import os
import json
import logging
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Union, Any
from src.core.services.gcs_service import GCSService

class TrackingService:
    def __init__(self, gcs_service: Optional[GCSService] = None):
        """
        Initialize the tracking service
        
        Args:
            gcs_service: Optional GCS service for cloud-based tracking
        """
        self.logger = logging.getLogger(__name__)
        self.gcs_service = gcs_service
        self.tracking_file = os.path.join(os.path.dirname(__file__), "../../../data/tracking.json")
        self.logger.info(f"Tracking service initialized with file path: {self.tracking_file}")
        self.records = self._load_records()
        self.logger.info(f"Loaded {len(self.records)} existing tracking records")
        
    def _load_records(self) -> List[Dict[str, Any]]:
        """Load records from tracking file or create empty list if file doesn't exist"""
        try:
            if os.path.exists(self.tracking_file):
                with open(self.tracking_file, 'r') as f:
                    return json.load(f)
            else:
                # Ensure directory exists
                os.makedirs(os.path.dirname(self.tracking_file), exist_ok=True)
                return []
        except Exception as e:
            self.logger.error(f"Error loading tracking records: {str(e)}")
            return []
            
    def _save_records(self) -> bool:
        """Save records to tracking file"""
        try:
            self.logger.info(f"Attempting to save {len(self.records)} records to {self.tracking_file}")
            with open(self.tracking_file, 'w') as f:
                json.dump(self.records, f, indent=2)
            self.logger.info("Successfully saved tracking records")
            return True
        except Exception as e:
            self.logger.error(f"Error saving tracking records: {str(e)}")
            return False
            
    def add_single_sample_record(self, sample_id: str, recipient_email: str, 
                              source_bucket: str, zip_file_path: str, 
                              expiration_days: int = 7) -> Dict[str, Any]:
        """
        Add a record for a single sample share
        
        Args:
            sample_id: ID of the shared sample
            recipient_email: Email of the recipient
            source_bucket: Source bucket name
            zip_file_path: Full GCS path to the shared zip file (e.g., "bucket/shared-zips/sample-123.zip")
            expiration_days: Days until the share expires
            
        Returns:
            The created record
        """
        now = datetime.now()
        expiration_date = now + timedelta(days=expiration_days)
        
        record = {
            "id": f"{sample_id}-{now.timestamp()}",
            "sample_id": sample_id,
            "recipient_email": recipient_email,
            "source_bucket": source_bucket,
            "zip_file_path": zip_file_path,  # Store the full path to the zip file
            "type": "single",
            "created_at": now.isoformat(),
            "expires_at": expiration_date.isoformat(),
            "active": True
        }
        
        self.records.append(record)
        self._save_records()
        
        return record
    
    def add_multi_sample_record(self, sample_ids: List[str], recipient_email: str,
                             source_bucket: str, destination_bucket: str,
                             expiration_days: int = 30) -> Dict[str, Any]:
        """
        Add a record for a multi-sample share
        
        Args:
            sample_ids: List of sample IDs shared
            recipient_email: Email of the recipient
            source_bucket: Source bucket name
            destination_bucket: Destination bucket name
            expiration_days: Days until the share expires
            
        Returns:
            The created record
        """
        now = datetime.now()
        expiration_date = now + timedelta(days=expiration_days)
        
        record = {
            "id": f"multi-{now.timestamp()}",
            "sample_count": len(sample_ids),
            "sample_ids": sample_ids,
            "recipient_email": recipient_email,
            "source_bucket": source_bucket,
            "destination": destination_bucket,
            "type": "multi",
            "created_at": now.isoformat(),
            "expires_at": expiration_date.isoformat(),
            "active": True
        }
        
        self.records.append(record)
        self._save_records()
        
        return record
        
    def reload_records(self) -> None:
        """Reload records from the tracking file"""
        self.records = self._load_records()
        self.logger.info(f"Reloaded {len(self.records)} tracking records from file")
        
    def get_all_records(self) -> pd.DataFrame:
        """
        Get all tracking records as a DataFrame
        
        Returns:
            DataFrame containing all tracking records
        """
        # Always reload from file to get the latest data
        self.reload_records()
        
        df = pd.DataFrame(self.records)
        if not df.empty:
            # Calculate days remaining
            df['created_at'] = pd.to_datetime(df['created_at'])
            df['expires_at'] = pd.to_datetime(df['expires_at'])
            now = datetime.now()
            df['days_remaining'] = (df['expires_at'] - pd.Timestamp(now)).dt.days
            
            # Only mark as expired if the expiration datetime has actually passed
            # Keep the original active status from the file unless truly expired
            now_timestamp = pd.Timestamp(now)
            df.loc[df['expires_at'] <= now_timestamp, 'active'] = False
            
            # Set negative days to 0 for display purposes, but don't change active status
            df.loc[df['days_remaining'] < 0, 'days_remaining'] = 0
            
        return df
        
    def update_record_status(self, record_id: str, active: bool) -> bool:
        """
        Update the active status of a record
        
        Args:
            record_id: ID of the record to update
            active: New active status
            
        Returns:
            Boolean indicating success
        """
        for record in self.records:
            if record.get('id') == record_id:
                record['active'] = active
                self._save_records()
                return True
                
        return False
        
    def get_expired_records(self) -> List[Dict[str, Any]]:
        """
        Get all expired records
        
        Returns:
            List of expired records
        """
        now = datetime.now()
        expired = []
        
        for record in self.records:
            expires_at = datetime.fromisoformat(record.get('expires_at'))
            if expires_at < now and record.get('active'):
                expired.append(record)
                
        return expired 