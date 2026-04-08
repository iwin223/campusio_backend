"""Paystack payment gateway integration"""
import httpx
import logging
import os
from typing import Dict, Optional
from datetime import datetime
import hmac
import hashlib
import json

logger = logging.getLogger(__name__)


class PaystackService:
    """Low-level Paystack API client"""
    
    BASE_URL = "https://api.paystack.co"
    
    def __init__(self, secret_key: str):
        self.secret_key = secret_key
    
    async def initialize_payment(
        self,
        amount_kobo: int,
        email: str,
        reference: str,
        metadata: Dict = None
    ) -> Dict:
        """
        Initialize payment with Paystack
        
        Args:
            amount_kobo: Amount in kobo (GHS 100 = 10000 kobo)
            email: Parent email address
            reference: Unique reference for this payment
            metadata: Additional data to pass through
        
        Returns:
            {
                "success": True,
                "authorization_url": "https://checkout.paystack.com/...",
                "access_code": "...",
                "reference": "..."
            }
        """
        headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "amount": amount_kobo,
            "email": email,
            "reference": reference,
            "metadata": metadata or {}
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.BASE_URL}/transaction/initialize",
                    headers=headers,
                    json=payload,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Payment initialized: {reference}")
                    return {
                        "success": True,
                        "authorization_url": data["data"]["authorization_url"],
                        "access_code": data["data"]["access_code"],
                        "reference": data["data"]["reference"]
                    }
                else:
                    logger.error(f"Paystack initialize failed: {response.text}")
                    return {
                        "success": False,
                        "error": response.json().get("message", "Payment initialization failed")
                    }
        
        except Exception as e:
            logger.error(f"Paystack API error: {str(e)}")
            return {
                "success": False,
                "error": f"Connection error: {str(e)}"
            }
    
    async def verify_payment(self, reference: str) -> Dict:
        """
        Verify payment status with Paystack
        
        Args:
            reference: Paystack transaction reference
        
        Returns:
            {
                "success": True,
                "data": {...full transaction data...},
                "status": "success" or "failed"
            }
        """
        headers = {
            "Authorization": f"Bearer {self.secret_key}"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/transaction/verify/{reference}",
                    headers=headers,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Payment verified: {reference}")
                    return {
                        "success": True,
                        "data": data["data"],
                        "status": data["data"]["status"]  # "success" or "failed"
                    }
                else:
                    logger.error(f"Paystack verify failed: {response.text}")
                    return {
                        "success": False,
                        "error": "Payment verification failed"
                    }
        
        except Exception as e:
            logger.error(f"Paystack verify error: {str(e)}")
            return {
                "success": False,
                "error": f"Verification error: {str(e)}"
            }
    
    @staticmethod
    def verify_webhook_signature(payload_bytes: bytes, signature: str, secret_key: str) -> bool:
        """
        Verify that webhook came from Paystack
        
        Args:
            payload_bytes: Raw webhook body
            signature: X-Paystack-Signature header
            secret_key: Your Paystack secret key
        
        Returns:
            True if signature is valid
        """
        hash = hmac.new(
            key=secret_key.encode(),
            msg=payload_bytes,
            digestmod=hashlib.sha512
        )
        computed_sig = hash.hexdigest()
        
        return hmac.compare_digest(computed_sig, signature)
