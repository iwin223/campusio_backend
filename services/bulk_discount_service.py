"""Bulk discount service for platform billing (Phase 2)"""
import logging
from typing import Optional, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from models.billing import DiscountRule, PlatformSubscription

logger = logging.getLogger(__name__)


class BulkDiscountService:
    """Manages bulk discount calculation and application"""
    
    async def get_applicable_discount(
        self,
        session: AsyncSession,
        school_id: str,
        student_count: int
    ) -> Dict:
        """
        Find applicable discount rule for school based on student count
        
        Returns:
        {
            "found": True,
            "discount_percentage": 5.0,
            "discount_amount": None,
            "reason": "500+ students get 5% off"
        }
        """
        try:
            # Get all active discount rules for school, ordered by min_students DESC
            result = await session.execute(
                select(DiscountRule)
                .where(
                    DiscountRule.school_id == school_id,
                    DiscountRule.is_active == True
                )
                .order_by(DiscountRule.min_students.desc())
            )
            rules = result.scalars().all()
            
            # Find highest applicable rule
            for rule in rules:
                if (student_count >= rule.min_students and
                    (rule.max_students is None or student_count <= rule.max_students)):
                    
                    logger.info(
                        f"Applied discount rule for school {school_id}: "
                        f"{student_count} students, {rule.discount_percentage}%"
                    )
                    
                    return {
                        "found": True,
                        "discount_percentage": rule.discount_percentage,
                        "discount_amount": rule.discount_amount,
                        "reason": rule.description,
                        "rule_id": rule.id
                    }
            
            return {"found": False}
            
        except Exception as e:
            logger.error(f"Error getting discount: {str(e)}")
            return {"found": False, "error": str(e)}
    
    async def calculate_discount(
        self,
        session: AsyncSession,
        school_id: str,
        subtotal: float,
        student_count: int
    ) -> Dict:
        """
        Calculate discount amount for subscription
        
        Returns amount and percentage to apply
        """
        discount_info = await self.get_applicable_discount(
            session,
            school_id,
            student_count
        )
        
        if not discount_info.get("found"):
            return {
                "discount_amount": 0.0,
                "discount_percentage": 0.0,
                "after_discount": subtotal,
                "reason": "No discount applicable"
            }
        
        # Calculate discount amount
        if discount_info.get("discount_amount"):
            # Fixed amount discount
            discount_amount = min(discount_info["discount_amount"], subtotal)
        else:
            # Percentage discount
            discount_percentage = discount_info.get("discount_percentage", 0)
            discount_amount = (subtotal * discount_percentage) / 100
        
        after_discount = max(0, subtotal - discount_amount)
        discount_percentage = discount_info.get("discount_percentage", 0)
        
        return {
            "discount_amount": round(discount_amount, 2),
            "discount_percentage": discount_percentage,
            "after_discount": round(after_discount, 2),
            "reason": discount_info.get("reason", "Bulk discount"),
            "rule_id": discount_info.get("rule_id")
        }
    
    async def create_discount_rule(
        self,
        session: AsyncSession,
        school_id: str,
        min_students: int,
        discount_percentage: Optional[float] = None,
        discount_amount: Optional[float] = None,
        max_students: Optional[int] = None,
        description: str = ""
    ) -> Dict:
        """Create a new discount rule for a school"""
        try:
            if not discount_percentage and not discount_amount:
                return {
                    "success": False,
                    "error": "Either discount_percentage or discount_amount required"
                }
            
            rule = DiscountRule(
                school_id=school_id,
                min_students=min_students,
                max_students=max_students,
                discount_percentage=discount_percentage or 0.0,
                discount_amount=discount_amount,
                description=description or f"{min_students}+ students discount",
                is_active=True
            )
            
            session.add(rule)
            await session.commit()
            
            logger.info(f"Created discount rule for {school_id}: {description}")
            
            return {
                "success": True,
                "rule_id": rule.id,
                "description": rule.description
            }
            
        except Exception as e:
            logger.error(f"Error creating discount rule: {str(e)}")
            await session.rollback()
            return {"success": False, "error": str(e)}
    
    async def list_discount_rules(
        self,
        session: AsyncSession,
        school_id: str
    ) -> list:
        """List all discount rules for a school"""
        try:
            result = await session.execute(
                select(DiscountRule)
                .where(DiscountRule.school_id == school_id)
                .order_by(DiscountRule.min_students)
            )
            rules = result.scalars().all()
            
            return [
                {
                    "id": rule.id,
                    "min_students": rule.min_students,
                    "max_students": rule.max_students,
                    "discount_percentage": rule.discount_percentage,
                    "discount_amount": rule.discount_amount,
                    "description": rule.description,
                    "is_active": rule.is_active
                }
                for rule in rules
            ]
            
        except Exception as e:
            logger.error(f"Error listing discount rules: {str(e)}")
            return []
    
    async def toggle_rule(
        self,
        session: AsyncSession,
        rule_id: str,
        is_active: bool
    ) -> Dict:
        """Enable/disable a discount rule"""
        try:
            result = await session.execute(
                select(DiscountRule).where(DiscountRule.id == rule_id)
            )
            rule = result.scalar_one_or_none()
            
            if not rule:
                return {"success": False, "error": "Rule not found"}
            
            rule.is_active = is_active
            await session.commit()
            
            status = "enabled" if is_active else "disabled"
            logger.info(f"Discount rule {rule_id} {status}")
            
            return {"success": True, "status": status}
            
        except Exception as e:
            logger.error(f"Error toggling rule: {str(e)}")
            await session.rollback()
            return {"success": False, "error": str(e)}
