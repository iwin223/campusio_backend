"""Chart of Accounts Service - Business logic for GL account management"""
import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, and_, or_
from datetime import datetime

from models.finance.chart_of_accounts import (
    GLAccount,
    GLAccountCreate,
    GLAccountUpdate,
    AccountType,
    AccountCategory,
)

logger = logging.getLogger(__name__)


class CoaServiceError(Exception):
    """Base exception for Chart of Accounts service errors"""
    pass


class CoaService:
    """Service for managing Chart of Accounts operations
    
    Handles:
    - GL account CRUD operations
    - Account code validation and uniqueness
    - Hierarchical account relationships
    - Account type and category queries
    - Activation/deactivation of accounts
    """
    
    def __init__(self, session: AsyncSession):
        """Initialize service with async database session
        
        Args:
            session: AsyncSession for database operations
        """
        self.session = session
    
    # ==================== Create Operations ====================
    
    async def create_account(
        self,
        school_id: str,
        account_data: GLAccountCreate,
        created_by: str
    ) -> GLAccount:
        """Create a new GL account
        
        Args:
            school_id: School identifier for multi-tenancy
            account_data: Account creation data
            created_by: User ID creating the account
            
        Returns:
            Created GLAccount instance
            
        Raises:
            CoaServiceError: If account code already exists for school
        """
        # Check uniqueness of account code within school
        existing = await self._get_account_by_code(school_id, account_data.account_code)
        if existing:
            raise CoaServiceError(
                f"Account code '{account_data.account_code}' already exists for this school"
            )
        
        # Validate parent account exists if specified
        if account_data.parent_account_id:
            parent = await self.get_account_by_id(school_id, account_data.parent_account_id)
            if not parent:
                raise CoaServiceError(f"Parent account '{account_data.parent_account_id}' not found")
        
        # Create new account
        account = GLAccount(
            school_id=school_id,
            account_code=account_data.account_code,
            account_name=account_data.account_name,
            account_type=account_data.account_type,
            account_category=account_data.account_category,
            description=account_data.description,
            normal_balance=account_data.normal_balance,
            parent_account_id=account_data.parent_account_id,
            created_by=created_by,
            is_active=True,
        )
        
        self.session.add(account)
        await self.session.commit()
        await self.session.refresh(account)
        
        logger.info(
            f"Created GL account {account.account_code} ({account.account_name}) "
            f"for school {school_id}"
        )
        
        return account
    
    # ==================== Read Operations ====================
    
    async def get_account_by_id(self, school_id: str, account_id: str) -> Optional[GLAccount]:
        """Get account by ID for a specific school
        
        Args:
            school_id: School identifier
            account_id: Account ID to retrieve
            
        Returns:
            GLAccount if found, None otherwise
        """
        try:
            result = await self.session.execute(
                select(GLAccount).where(
                    and_(
                        GLAccount.school_id == school_id,
                        GLAccount.id == account_id
                    )
                )
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error fetching account {account_id}: {str(e)}")
            return None
    
    async def get_account_by_code(self, school_id: str, account_code: str) -> Optional[GLAccount]:
        """Get account by account code for a specific school
        
        Args:
            school_id: School identifier
            account_code: Account code (e.g., "1010", "5100")
            
        Returns:
            GLAccount if found, None otherwise
        """
        return await self._get_account_by_code(school_id, account_code)
    
    async def _get_account_by_code(self, school_id: str, account_code: str) -> Optional[GLAccount]:
        """Internal method to get account by code
        
        Args:
            school_id: School identifier
            account_code: Account code
            
        Returns:
            GLAccount if found, None otherwise
        """
        try:
            result = await self.session.execute(
                select(GLAccount).where(
                    and_(
                        GLAccount.school_id == school_id,
                        GLAccount.account_code == account_code
                    )
                )
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error fetching account by code {account_code}: {str(e)}")
            return None
    
    async def get_all_accounts(
        self,
        school_id: str,
        active_only: bool = True,
        account_type: Optional[AccountType] = None,
        account_category: Optional[AccountCategory] = None,
    ) -> List[GLAccount]:
        """Get all GL accounts with optional filtering
        
        Args:
            school_id: School identifier
            active_only: Filter to active accounts only (default: True)
            account_type: Filter by account type (optional)
            account_category: Filter by account category (optional)
            
        Returns:
            List of GLAccount instances
        """
        try:
            query = select(GLAccount).where(GLAccount.school_id == school_id)
            
            if active_only:
                query = query.where(GLAccount.is_active == True)
            
            if account_type:
                query = query.where(GLAccount.account_type == account_type)
            
            if account_category:
                query = query.where(GLAccount.account_category == account_category)
            
            # Order by account code for easy scanning
            query = query.order_by(GLAccount.account_code)
            
            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error fetching accounts for school {school_id}: {str(e)}")
            return []
    
    async def get_accounts_by_type(
        self,
        school_id: str,
        account_type: AccountType,
        active_only: bool = True,
    ) -> List[GLAccount]:
        """Get all accounts of a specific type
        
        Args:
            school_id: School identifier
            account_type: Account type to filter by
            active_only: Filter to active accounts only
            
        Returns:
            List of GLAccount instances
        """
        return await self.get_all_accounts(
            school_id=school_id,
            active_only=active_only,
            account_type=account_type
        )
    
    async def get_accounts_by_category(
        self,
        school_id: str,
        account_category: AccountCategory,
        active_only: bool = True,
    ) -> List[GLAccount]:
        """Get all accounts in a specific category
        
        Args:
            school_id: School identifier
            account_category: Account category to filter by
            active_only: Filter to active accounts only
            
        Returns:
            List of GLAccount instances
        """
        return await self.get_all_accounts(
            school_id=school_id,
            active_only=active_only,
            account_category=account_category
        )
    
    async def get_sub_accounts(
        self,
        school_id: str,
        parent_account_id: str,
        active_only: bool = True,
    ) -> List[GLAccount]:
        """Get all sub-accounts under a parent account (hierarchical)
        
        Args:
            school_id: School identifier
            parent_account_id: Parent account ID
            active_only: Filter to active accounts only
            
        Returns:
            List of child GLAccount instances
        """
        try:
            query = select(GLAccount).where(
                and_(
                    GLAccount.school_id == school_id,
                    GLAccount.parent_account_id == parent_account_id
                )
            )
            
            if active_only:
                query = query.where(GLAccount.is_active == True)
            
            query = query.order_by(GLAccount.account_code)
            
            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error fetching sub-accounts for {parent_account_id}: {str(e)}")
            return []
    
    # ==================== Update Operations ====================
    
    async def update_account(
        self,
        school_id: str,
        account_id: str,
        update_data: GLAccountUpdate,
    ) -> Optional[GLAccount]:
        """Update an existing GL account
        
        Args:
            school_id: School identifier
            account_id: Account ID to update
            update_data: Fields to update
            
        Returns:
            Updated GLAccount instance, or None if not found
        """
        account = await self.get_account_by_id(school_id, account_id)
        if not account:
            logger.warning(f"Attempt to update non-existent account {account_id}")
            return None
        
        # Update fields that are provided
        update_dict = update_data.model_dump(exclude_unset=True)
        
        for key, value in update_dict.items():
            setattr(account, key, value)
        
        account.updated_at = datetime.utcnow()
        
        self.session.add(account)
        await self.session.commit()
        await self.session.refresh(account)
        
        logger.info(f"Updated GL account {account.account_code} for school {school_id}")
        
        return account
    
    # ==================== Deactivation Operations ====================
    
    async def deactivate_account(self, school_id: str, account_id: str) -> Optional[GLAccount]:
        """Deactivate (soft delete) a GL account
        
        Deactivation is used instead of hard delete to maintain audit trail and prevent
        orphaned journal entries from referencing deleted accounts.
        
        Args:
            school_id: School identifier
            account_id: Account ID to deactivate
            
        Returns:
            Deactivated GLAccount instance, or None if not found
        """
        account = await self.get_account_by_id(school_id, account_id)
        if not account:
            return None
        
        account.is_active = False
        account.updated_at = datetime.utcnow()
        
        self.session.add(account)
        await self.session.commit()
        await self.session.refresh(account)
        
        logger.info(f"Deactivated GL account {account.account_code} for school {school_id}")
        
        return account
    
    async def activate_account(self, school_id: str, account_id: str) -> Optional[GLAccount]:
        """Reactivate a previously deactivated GL account
        
        Args:
            school_id: School identifier
            account_id: Account ID to reactivate
            
        Returns:
            Reactivated GLAccount instance, or None if not found
        """
        account = await self.get_account_by_id(school_id, account_id)
        if not account:
            return None
        
        account.is_active = True
        account.updated_at = datetime.utcnow()
        
        self.session.add(account)
        await self.session.commit()
        await self.session.refresh(account)
        
        logger.info(f"Reactivated GL account {account.account_code} for school {school_id}")
        
        return account
    
    # ==================== Validation & Analysis Operations ====================
    
    async def validate_account_code_exists(self, school_id: str, account_code: str) -> bool:
        """Check if an account code exists for a school
        
        Args:
            school_id: School identifier
            account_code: Account code to check
            
        Returns:
            True if account exists, False otherwise
        """
        account = await self._get_account_by_code(school_id, account_code)
        return account is not None
    
    async def get_account_balance_summary(self, school_id: str) -> Dict[str, Any]:
        """Get summary of accounts by type and category
        
        Useful for dashboard overviews and validation checks.
        
        Args:
            school_id: School identifier
            
        Returns:
            Dictionary with account counts and totals by type/category
        """
        try:
            all_accounts = await self.get_all_accounts(school_id, active_only=True)
            
            summary = {
                "total_accounts": len(all_accounts),
                "by_type": {},
                "by_category": {},
            }
            
            # Count by account type
            for account_type in AccountType:
                count = sum(1 for acc in all_accounts if acc.account_type == account_type)
                if count > 0:
                    summary["by_type"][account_type.value] = count
            
            # Count by account category
            for account_category in AccountCategory:
                count = sum(1 for acc in all_accounts if acc.account_category == account_category)
                if count > 0:
                    summary["by_category"][account_category.value] = count
            
            return summary
        except Exception as e:
            logger.error(f"Error generating account summary for school {school_id}: {str(e)}")
            return {"error": str(e)}
