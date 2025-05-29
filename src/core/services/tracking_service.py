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
        self.records = self._load_records()
        
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
            with open(self.tracking_file, 'w') as f:
                json.dump(self.records, f, indent=2)
            return True
        except Exception as e:
            self.logger.error(f"Error saving tracking records: {str(e)}")
            return False
            
    def add_single_sample_record(self, sample_id: str, recipient_email: str, 
                              source_bucket: str, temp_bucket: str, 
                              expiration_days: int = 7) -> Dict[str, Any]:
        """
        Add a record for a single sample share
        
        Args:
            sample_id: ID of the shared sample
            recipient_email: Email of the recipient
            source_bucket: Source bucket name
            temp_bucket: Temporary bucket where sample is shared
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
            "destination": temp_bucket,
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
        
    def get_all_records(self) -> pd.DataFrame:
        """
        Get all tracking records as a DataFrame
        
        Returns:
            DataFrame containing all tracking records
        """
        df = pd.DataFrame(self.records)
        if not df.empty:
            # Calculate days remaining
            df['created_at'] = pd.to_datetime(df['created_at'])
            df['expires_at'] = pd.to_datetime(df['expires_at'])
            now = datetime.now()
            df['days_remaining'] = (df['expires_at'] - pd.Timestamp(now)).dt.days
            
            # Set negative days to 0 and mark as expired
            df.loc[df['days_remaining'] < 0, 'days_remaining'] = 0
            df.loc[df['days_remaining'] == 0, 'active'] = False
            
        return df
        
    def delete_record(self, record_id: str, cleanup_gcs: bool = True) -> bool:
        """
        Delete a tracking record and optionally cleanup GCS resources
        
        Args:
            record_id: ID of the record to delete
            cleanup_gcs: Whether to delete associated GCS resources
            
        Returns:
            Boolean indicating success
        """
        for i, record in enumerate(self.records):
            if record.get('id') == record_id:
                if cleanup_gcs and self.gcs_service:
                    try:
                        if record.get('type') == 'single':
                            # Delete the temporary bucket for single samples
                            bucket_name = record.get('destination')
                            if bucket_name:
                                # Delete all objects first
                                objects = self.gcs_service.list_objects(bucket_name)
                                for obj in objects:
                                    self.gcs_service.delete_object(bucket_name, obj.name)
                        # For multi-sample, we don't delete the destination bucket automatically
                        # as it might contain other data or be managed separately
                    except Exception as e:
                        self.logger.error(f"Error cleaning up GCS resources: {str(e)}")
                
                # Delete the record
                del self.records[i]
                self._save_records()
                return True
                
        return False
        
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