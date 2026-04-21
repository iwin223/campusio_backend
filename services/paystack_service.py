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
        
        logger.info(f"Paystack request - Amount: {amount_kobo}, Email: {email}, Ref: {reference}")
        
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
                    error_data = response.json()
                    error_msg = error_data.get("message", "Payment initialization failed")
                    logger.error(f"Paystack initialize failed (status {response.status_code}): {error_msg}")
                    logger.error(f"Full response: {response.text}")
                    return {
                        "success": False,
                        "error": error_msg
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
    
    async def get_account_balance(self) -> Dict:
        """
        Get current Paystack account balance
        
        Returns:
        {
            "success": True,
            "balance": 50000,  # in kobo
            "currency": "GHS"
        }
        """
        headers = {
            "Authorization": f"Bearer {self.secret_key}"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/balance",
                    headers=headers,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    # Convert kobo to GHS
                    balance_ghs = data["data"][0]["balance"] / 100 if data["data"] else 0
                    logger.info(f"Balance fetched: GHS {balance_ghs}")
                    return {
                        "success": True,
                        "balance": balance_ghs,
                        "currency": "GHS"
                    }
                else:
                    logger.error(f"Balance fetch failed: {response.text}")
                    return {
                        "success": False,
                        "error": "Failed to fetch balance",
                        "balance": 0
                    }
        
        except Exception as e:
            logger.error(f"Balance error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "balance": 0
            }
    
    async def create_transfer_recipient(
        self,
        type_: str,
        account_number: str,
        account_name: str,
        currency: str = "GHS",
        bank_code: str = None
    ) -> Dict:
        """
        Create a transfer recipient (MoMo or bank account)
        
        Args:
            type_: "mobile_money" or "nuban"
            account_number: MoMo number or bank account
            account_name: Name of recipient
            currency: "GHS"
            bank_code: Bank code (e.g., "MTN", "VOD", "ATL" for mobile_money)
        
        Returns:
        {
            "success": True,
            "recipient_code": "RCP_xxx",
            "account_number": "...",
            "account_name": "..."
        }
        """
        headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "type": type_,
            "account_number": account_number,
            "account_name": account_name,
            "currency": currency
        }
        
        # Add bank_code for mobile_money transfers (required by Paystack for Ghana)
        if type_ == "mobile_money" and bank_code:
            payload["bank_code"] = bank_code
            logger.info(f"Adding bank_code {bank_code} for MoMo transfer to {account_number}")
        
        logger.debug(f"Transfer recipient payload: {payload}")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.BASE_URL}/transferrecipient",
                    headers=headers,
                    json=payload,
                    timeout=10.0
                )
                
                if response.status_code == 201:
                    data = response.json()
                    logger.debug(f"Paystack response data: {data}")
                    
                    # Extract recipient data safely
                    recipient_data = data.get("data", {})
                    return {
                        "success": True,
                        "recipient_code": recipient_data.get("recipient_code", ""),
                        "account_number": recipient_data.get("account_number", account_number),
                        "account_name": recipient_data.get("account_name", account_name)
                    }
                else:
                    logger.error(f"Recipient creation failed: {response.text}")
                    return {
                        "success": False,
                        "error": response.json().get("message", "Failed to create recipient")
                    }
        
        except Exception as e:
            logger.error(f"Recipient creation error: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": f"Recipient creation failed: {str(e)}"
            }
    
    async def initiate_transfer(
        self,
        source: str,
        amount: int,
        recipient_code: str,
        reason: str,
        reference: str
    ) -> Dict:
        """
        Initiate a transfer to recipient
        
        Args:
            source: "balance" (transfer from Paystack balance)
            amount: Amount in kobo
            recipient_code: Recipient code from create_transfer_recipient
            reason: Transfer description
            reference: Unique reference for tracking
        
        Returns:
        {
            "success": True,
            "transfer_code": "TRF_xxx",
            "reference": "...",
            "amount": 50000,
            "status": "pending"
        }
        """
        headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "source": source,
            "amount": amount,
            "recipient": recipient_code,
            "reason": reason,
            "reference": reference
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.BASE_URL}/transfer",
                    headers=headers,
                    json=payload,
                    timeout=10.0
                )
                
                if response.status_code in [200, 201]:
                    data = response.json()
                    logger.debug(f"Paystack transfer response: {data}")
                    
                    # Extract transfer data safely
                    transfer_data = data.get("data", {})
                    return {
                        "success": True,
                        "transfer_code": transfer_data.get("transfer_code", ""),
                        "reference": transfer_data.get("reference", reference),
                        "amount": transfer_data.get("amount", amount) / 100,  # Convert to GHS
                        "status": transfer_data.get("status", "pending"),
                        "recipient": transfer_data.get("recipient", recipient_code)
                    }
                else:
                    logger.error(f"Transfer initiation failed: {response.text}")
                    return {
                        "success": False,
                        "error": response.json().get("message", "Transfer initiation failed")
                    }
        
        except Exception as e:
            logger.error(f"Transfer initiation error: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    async def verify_transfer(self, transfer_code: str) -> Dict:
        """
        Verify status of a transfer
        
        Args:
            transfer_code: Paystack transfer code
        
        Returns:
        {
            "success": True,
            "transfer_code": "TRF_xxx",
            "status": "success|pending|failed",
            "amount": 50000,
            "reason": "..."
        }
        """
        headers = {
            "Authorization": f"Bearer {self.secret_key}"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/transfer/verify/{transfer_code}",
                    headers=headers,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "transfer_code": data["data"]["transfer_code"],
                        "status": data["data"]["status"],
                        "amount": data["data"]["amount"] / 100,
                        "reason": data["data"]["reason"]
                    }
                else:
                    logger.error(f"Transfer verification failed: {response.text}")
                    return {
                        "success": False,
                        "error": "Transfer verification failed"
                    }
        
        except Exception as e:
            logger.error(f"Transfer verification error: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
