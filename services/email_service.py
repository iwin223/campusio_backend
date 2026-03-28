"""Email Service using Elastic Email API"""
import httpx
import logging
from typing import List, Dict, Optional
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class EmailService:
    """Elastic Email Service for sending transactional emails"""
    
    BASE_URL = "https://api.elasticemail.com/v4"
    
    def __init__(self):
        self.api_key = settings.elastic_email_api_key
        self.from_email = settings.elastic_email_from_email
        self.from_name = settings.elastic_email_from_name
        
    def _get_headers(self) -> Dict:
        """Get request headers with API key"""
        return {
            "X-ElasticEmail-ApiKey": self.api_key,
            "Content-Type": "application/json"
        }
    
    async def send_email(
        self,
        to: List[str],
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
        reply_to: Optional[str] = None
    ) -> Dict:
        """
        Send a transactional email
        
        Args:
            to: List of recipient email addresses
            subject: Email subject line
            html_body: HTML content of the email
            text_body: Plain text alternative (optional)
            reply_to: Reply-to email address (optional)
        
        Returns:
            Response from Elastic Email API
        """
        if not self.api_key:
            logger.warning("Elastic Email API key not configured - email not sent")
            return {"success": False, "error": "Email service not configured"}
        
        try:
            recipients = [{"Email": email} for email in to]
            
            body = [
                {
                    "ContentType": "HTML",
                    "Content": html_body,
                    "Charset": "utf-8"
                }
            ]
            
            if text_body:
                body.append({
                    "ContentType": "PlainText",
                    "Content": text_body,
                    "Charset": "utf-8"
                })
            
            payload = {
                "Recipients": recipients,
                "Content": {
                    "Body": body,
                    "From": f"{self.from_name} <{self.from_email}>",
                    "ReplyTo": reply_to or self.from_email,
                    "Subject": subject
                }
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.BASE_URL}/emails/transactional",
                    json=payload,
                    headers=self._get_headers(),
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Email sent successfully to {len(to)} recipient(s)")
                    return {"success": True, "message_id": data.get("MessageID")}
                else:
                    error_msg = response.text
                    logger.error(f"Failed to send email: {error_msg}")
                    return {"success": False, "error": error_msg}
                    
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def send_announcement_email(
        self,
        to: List[str],
        title: str,
        content: str,
        announcement_type: str = "general",
        school_name: str = "School ERP"
    ) -> Dict:
        """Send an announcement email with formatted template"""
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: 'IBM Plex Sans', Arial, sans-serif; color: #1A1A1A; line-height: 1.6; margin: 0; padding: 0; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; background-color: #FAFAED; }}
                .header {{ background-color: #064E3B; color: white; padding: 24px; text-align: center; border-radius: 12px 12px 0 0; }}
                .header h1 {{ margin: 0; font-size: 24px; font-family: 'Manrope', sans-serif; }}
                .content {{ background-color: white; padding: 24px; border: 1px solid #E4E4E7; border-top: none; border-radius: 0 0 12px 12px; }}
                .badge {{ display: inline-block; padding: 4px 12px; border-radius: 9999px; font-size: 12px; font-weight: 500; background-color: #064E3B; color: white; text-transform: capitalize; margin-bottom: 16px; }}
                .title {{ font-size: 20px; font-weight: 600; color: #1A1A1A; margin-bottom: 12px; }}
                .message {{ color: #52525B; margin-bottom: 24px; }}
                .footer {{ text-align: center; font-size: 12px; color: #A1A1AA; margin-top: 24px; padding-top: 16px; border-top: 1px solid #E4E4E7; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>{school_name}</h1>
                </div>
                <div class="content">
                    <span class="badge">{announcement_type}</span>
                    <h2 class="title">{title}</h2>
                    <p class="message">{content}</p>
                </div>
                <div class="footer">
                    <p>This is an automated message from {school_name}.</p>
                    <p>Please do not reply directly to this email.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_body = f"""
{school_name} - {announcement_type.upper()} Announcement

{title}

{content}

---
This is an automated message. Please do not reply directly to this email.
        """
        
        return await self.send_email(
            to=to,
            subject=f"[{announcement_type.capitalize()}] {title}",
            html_body=html_body,
            text_body=text_body
        )
    
    async def send_fee_reminder(
        self,
        to: str,
        student_name: str,
        student_id: str,
        amount_due: float,
        due_date: str,
        school_name: str = "School ERP"
    ) -> Dict:
        """Send a fee reminder email"""
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: 'IBM Plex Sans', Arial, sans-serif; color: #1A1A1A; line-height: 1.6; margin: 0; padding: 0; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; background-color: #FAFAED; }}
                .header {{ background-color: #064E3B; color: white; padding: 24px; text-align: center; border-radius: 12px 12px 0 0; }}
                .content {{ background-color: white; padding: 24px; border: 1px solid #E4E4E7; border-top: none; border-radius: 0 0 12px 12px; }}
                .amount {{ font-size: 32px; font-weight: 700; color: #9A3412; margin: 20px 0; font-family: 'JetBrains Mono', monospace; }}
                .info-table {{ width: 100%; margin: 20px 0; }}
                .info-table td {{ padding: 8px 0; }}
                .info-table td:first-child {{ color: #52525B; }}
                .info-table td:last-child {{ font-weight: 500; text-align: right; }}
                .button {{ display: inline-block; background-color: #064E3B; color: white; padding: 12px 32px; text-decoration: none; border-radius: 9999px; font-weight: 500; margin-top: 16px; }}
                .footer {{ text-align: center; font-size: 12px; color: #A1A1AA; margin-top: 24px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Fee Reminder</h1>
                </div>
                <div class="content">
                    <p>Dear Parent/Guardian,</p>
                    <p>This is a friendly reminder that school fees are due for your child.</p>
                    
                    <table class="info-table">
                        <tr>
                            <td>Student Name:</td>
                            <td>{student_name}</td>
                        </tr>
                        <tr>
                            <td>Student ID:</td>
                            <td style="font-family: 'JetBrains Mono', monospace;">{student_id}</td>
                        </tr>
                        <tr>
                            <td>Due Date:</td>
                            <td>{due_date}</td>
                        </tr>
                    </table>
                    
                    <p class="amount">GHS {amount_due:,.2f}</p>
                    
                    <p>Please make payment at the school's administration office or through our designated payment channels.</p>
                    
                    <p>If you have already made this payment, please disregard this reminder.</p>
                </div>
                <div class="footer">
                    <p>{school_name}</p>
                    <p>This is an automated message.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return await self.send_email(
            to=[to],
            subject=f"Fee Reminder: {student_name} - GHS {amount_due:,.2f} Due",
            html_body=html_body
        )


# Singleton instance
email_service = EmailService()
