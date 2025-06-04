import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional, Dict
from datetime import datetime, timedelta

class EmailService:
    def __init__(self):
        """Initialize the SMTP email client using environment variables"""
        # Email server settings
        self.smtp_server = os.environ.get("EMAIL_SMTP_SERVER")
        if not self.smtp_server:
            raise ValueError("EMAIL_SMTP_SERVER environment variable not set")
            
        self.smtp_port = int(os.environ.get("EMAIL_SMTP_PORT", "587"))
        self.use_tls = os.environ.get("EMAIL_USE_TLS", "True").lower() == "true"
        
        # Authentication credentials
        self.username = os.environ.get("EMAIL_USERNAME")
        if not self.username:
            raise ValueError("EMAIL_USERNAME environment variable not set")
            
        self.password = os.environ.get("EMAIL_PASSWORD")
        if not self.password:
            raise ValueError("EMAIL_PASSWORD environment variable not set")
            
        self.from_email = os.environ.get("EMAIL_FROM_ADDRESS", self.username)
        self.logger = logging.getLogger(__name__)
        
    def send_single_sample_notification(self, recipient_email: str, sample_id: str, 
                                      download_url: Optional[str] = None, 
                                      download_urls: Optional[List[Dict[str, str]]] = None,
                                      expires_days: int = 7) -> bool:
        """
        Send a notification email with download links for a single sample
        
        Args:
            recipient_email: Email address of the recipient
            sample_id: ID of the sample being shared
            download_url: Single signed URL for downloading (backward compatibility)
            download_urls: List of dicts with 'filename' and 'url' keys
            expires_days: Number of days until the links expire
            
        Returns:
            Boolean indicating success or failure
        """
        subject = f"PD GENEration Raw Genetic Data - Sample {sample_id}"
        
        # Build download links HTML
        if download_urls:
            links_html = ""
            for file_info in download_urls:
                filename = file_info['filename'].split('/')[-1]  # Get just the filename
                links_html += f'<a href="{file_info["url"]}">{filename}</a><br>'
        elif download_url:
            # Single download link
            links_html = f'<a href="{download_url}">Download your data</a>'
        else:
            links_html = "[Download link not available]"
        
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <p>Hello,</p>
                
                <p>Thank you for your interest in receiving raw genetic data files from the PD GENEration study.</p>
                
                <p>Please use the following link to access the data: {links_html}</p>
                
                <p>As per our last email, this link will only work if the email address to which you received this 
                communication has been associated with a Google account.</p>
                
                <p>Of note, the raw genetic data can be rather large. It will download in a .zip format that itself may 
                be up to 4 GB in size, and the uncompressed data can be &gt;50 GB in size. Please ensure that 
                your computer is able to handle this amount of data or that you are able to transfer the data into 
                your own Cloud platform.</p>
                
                <p>You will have {expires_days} days to download the files before the above link expires.</p>
                
                <p>If you have any questions, please feel free to reach out to 
                <a href="mailto:PDGENEData@parkinson.org">PDGENEData@parkinson.org</a> or 
                contact your PD GENEration study site. You may also call the Parkinson's Foundation helpline 
                at 1-800-4PD-INFO.</p>
                
                <p>Have a great day.</p>
                
                <p>Best regards,<br>
                The PD GENEration Team</p>
            </body>
        </html>
        """
        
        # Create a message
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = self.from_email
        message["To"] = recipient_email
        
        # Create HTML content
        html_part = MIMEText(html_content, "html")
        message.attach(html_part)
        
        try:
            # Connect to the SMTP server
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                    
                server.login(self.username, self.password)
                server.sendmail(self.from_email, recipient_email, message.as_string())
                
            self.logger.info(f"Email sent successfully to {recipient_email} for sample {sample_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending email: {str(e)}")
            return False
            
    def send_multi_sample_notification(self, recipient_email: str, sample_ids: List[str],
                                     bucket_name: str, expires_days: int = 30) -> bool:
        """
        Send a notification email about multiple samples shared in a bucket
        
        Args:
            recipient_email: Email address of the recipient
            sample_ids: List of sample IDs that were shared
            bucket_name: Name of the GCS bucket where samples were shared
            expires_days: Number of days until the data expires
            
        Returns:
            Boolean indicating success or failure
        """
        subject = f"PD GENEration Raw Genetic Data - Multiple Samples Available"
        
        # Format the sample IDs for display
        if len(sample_ids) > 10:
            sample_display = "<br>• ".join(sample_ids[:10]) + f"<br>• ... and {len(sample_ids) - 10} more"
        else:
            sample_display = "<br>• ".join(sample_ids)
        
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <p>Hello,</p>
                
                <p>Thank you for your interest in receiving raw genetic data files from the PD GENEration study.</p>
                
                <p>The following samples are now available in Google Cloud Storage bucket <strong>{bucket_name}</strong>:</p>
                
                <p style="margin-left: 20px;">
                • {sample_display}
                </p>
                
                <p>You have been granted access to this bucket. To access the data, please use the Google Cloud Console 
                or the gsutil command-line tool. As per our last email, this access will only work if the email address 
                to which you received this communication has been associated with a Google account.</p>
                
                <p>Of note, the raw genetic data can be rather large. Each sample may contain files that are several GB 
                in size. Please ensure that your computer or Cloud platform can handle this amount of data.</p>
                
                <p>You will have {expires_days} days to download the files before access expires.</p>
                
                <p>If you have any questions, please feel free to reach out to 
                <a href="mailto:PDGENEData@parkinson.org">PDGENEData@parkinson.org</a> or 
                contact your PD GENEration study site. You may also call the Parkinson's Foundation helpline 
                at 1-800-4PD-INFO.</p>
                
                <p>Have a great day.</p>
                
                <p>Best regards,<br>
                The PD GENEration Team</p>
            </body>
        </html>
        """
        
        # Create a message
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = self.from_email
        message["To"] = recipient_email
        
        # Create HTML content
        html_part = MIMEText(html_content, "html")
        message.attach(html_part)
        
        try:
            # Connect to the SMTP server
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                    
                server.login(self.username, self.password)
                server.sendmail(self.from_email, recipient_email, message.as_string())
                
            self.logger.info(f"Email sent successfully to {recipient_email} for multiple samples")
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending email: {str(e)}")
            return False 