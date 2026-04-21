"""Notification service for ticketing system - SMS via USMS"""
import logging
from typing import Dict
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class SMSNotificationService:
    """Send notifications via SMS using USMS API"""
    
    def __init__(self):
        from services.sms_service import SMSService
        self.sms = SMSService()
    
    async def send_ticket_created(
        self,
        school_name: str,
        ticket_title: str,
        ticket_priority: str,
        ticket_id: str,
        superadmin_phone: str
    ) -> Dict:
        """Send SMS notification when ticket is created"""
        
        message = f"NEW TICKET from {school_name}: {ticket_title[:40]} (Priority: {ticket_priority.upper()}) ID: {ticket_id[:8]}"
        
        try:
            result = await self.sms.send_sms([superadmin_phone], message)
            logger.info(f"SMS ticket created notification sent to {superadmin_phone}")
            return result
        except Exception as e:
            logger.error(f"Failed to send SMS notification: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "status": "error"
            }
    
    async def send_ticket_status_update(
        self,
        school_name: str,
        ticket_title: str,
        new_status: str,
        school_admin_phone: str
    ) -> Dict:
        """Send SMS update to school when status changes"""
        
        status_text = new_status.replace('_', ' ').title()
        message = f"TICKET UPDATE from {school_name}: {ticket_title[:35]} - Status: {status_text}"
        
        try:
            result = await self.sms.send_sms([school_admin_phone], message)
            logger.info(f"SMS status update notification sent to {school_admin_phone}")
            return result
        except Exception as e:
            logger.error(f"Failed to send SMS update notification: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "status": "error"
            }
    
    async def send_ticket_closed(
        self,
        school_name: str,
        ticket_title: str,
        resolution: str,
        school_admin_phone: str
    ) -> Dict:
        """Send SMS notification when ticket is closed"""
        
        resolution_text = resolution[:50] + "..." if len(resolution) > 50 else resolution
        message = f"TICKET CLOSED from {school_name}: {ticket_title[:35]} - Resolution: {resolution_text}"
        
        try:
            result = await self.sms.send_sms([school_admin_phone], message)
            logger.info(f"SMS ticket closed notification sent to {school_admin_phone}")
            return result
        except Exception as e:
            logger.error(f"Failed to send SMS closed notification: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "status": "error"
            }

