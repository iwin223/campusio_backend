"""Chart of Accounts Initialization and Seeding
Provides functions to set up default Chart of Accounts for new schools
"""
import logging
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from models.finance.seed_coa import DEFAULT_CHART_OF_ACCOUNTS
from models.finance.chart_of_accounts import GLAccountCreate, AccountCategory
from services.coa_service import CoaService

logger = logging.getLogger(__name__)


async def seed_default_chart_of_accounts(
    session: AsyncSession,
    school_id: str,
    created_by: str = "system"
) -> Dict[str, Any]:
    """Initialize default Chart of Accounts for a school
    
    This function is called when a new school is created in the system.
    It populates the school's GL with a standard chart of accounts configured
    for Ghanaian educational institutions.
    
    Args:
        session: Async database session
        school_id: ID of the school to initialize
        created_by: User ID creating the accounts (default: "system")
        
    Returns:
        Dictionary with seeding results:
        {
            "success": bool,
            "accounts_created": int,
            "accounts_failed": int,
            "errors": List[str]
        }
    """
    coa_service = CoaService(session)
    results = {
        "success": True,
        "accounts_created": 0,
        "accounts_failed": 0,
        "errors": [],
    }
    
    try:
        logger.info(f"Seeding default Chart of Accounts for school {school_id}")
        
        for account_data_dict in DEFAULT_CHART_OF_ACCOUNTS:
            try:
                account_data = GLAccountCreate(**account_data_dict)
                await coa_service.create_account(
                    school_id=school_id,
                    account_data=account_data,
                    created_by=created_by
                )
                results["accounts_created"] += 1
            except Exception as e:
                error_msg = (
                    f"Failed to create account {account_data_dict.get('account_code')}: {str(e)}"
                )
                logger.error(error_msg)
                results["errors"].append(error_msg)
                results["accounts_failed"] += 1
        
        if results["accounts_failed"] == 0:
            logger.info(
                f"Successfully seeded {results['accounts_created']} accounts "
                f"for school {school_id}"
            )
        else:
            logger.warning(
                f"Seeding completed with {results['accounts_failed']} failures "
                f"for school {school_id}"
            )
            results["success"] = False
        
        return results
        
    except Exception as e:
        error_msg = f"Critical error seeding accounts for school {school_id}: {str(e)}"
        logger.error(error_msg)
        results["success"] = False
        results["errors"].append(error_msg)
        return results


async def validate_school_chart_of_accounts(
    session: AsyncSession,
    school_id: str
) -> Dict[str, Any]:
    """Validate that a school has required GL accounts configured
    
    Checks that critical accounts exist for:
    - Bank accounts (at least one)
    - Payroll accounts (salaries payable, expenses)
    - Fee revenue accounts (at least one)
    - Expense accounts (for operations)
    
    Args:
        session: Async database session
        school_id: ID of school to validate
        
    Returns:
        Validation result dictionary
    """
    coa_service = CoaService(session)
    validation = {
        "is_valid": True,
        "missing_accounts": [],
        "warnings": [],
    }
    
    try:
        # Critical accounts that should exist
        critical_accounts = [
            ("1010", "Business Checking Account"),  # Bank asset
            ("1100", "Accounts Receivable - Student Fees"),  # Revenue tracking
            ("2100", "Salaries Payable"),  # Payroll liability
            ("4100", "Student Tuition Fees"),  # Revenue
            ("5100", "Salaries and Wages"),  # Expense
        ]
        
        for account_code, account_name in critical_accounts:
            account = await coa_service.get_account_by_code(school_id, account_code)
            if not account:
                validation["is_valid"] = False
                validation["missing_accounts"].append({
                    "code": account_code,
                    "name": account_name,
                })
        
        # Warnings for recommended accounts
        bank_accounts = await coa_service.get_accounts_by_category(
            school_id, AccountCategory.BANK_ACCOUNTS
        )
        if len(bank_accounts) < 2:
            validation["warnings"].append(
                "School has fewer than 2 bank accounts. Consider adding a savings account."
            )
        
        return validation
        
    except Exception as e:
        logger.error(f"Error validating CoA for school {school_id}: {str(e)}")
        return {
            "is_valid": False,
            "error": str(e),
        }
