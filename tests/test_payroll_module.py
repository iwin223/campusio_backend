"""
Payroll Module Tests - School ERP System
Tests for contract management, payroll calculations, and run generation
"""
import pytest
import asyncio
from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from models.payroll import (
    PayrollContract, PayrollRun, PayrollLineItem, PayrollStatus,
    PaySchedule, PayrollCategory
)
from models.staff import Staff, StaffStatus, StaffType
from models.user import User, UserRole
from models.school import School
from services.payroll_service import PayrollService, PayrollCalculationError


# ================ Test Fixtures ================ 

@pytest.fixture
async def test_db():
    """Create test database session"""
    # Use in-memory SQLite for tests
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
    
    await engine.dispose()


@pytest.fixture
def sample_contract():
    """Create a sample payroll contract"""
    return PayrollContract(
        id="test-contract-001",
        school_id="test-school-001",
        staff_id="test-staff-001",
        basic_salary=5000.0,
        pay_schedule=PaySchedule.MONTHLY,
        currency="GHS",
        allowance_housing=500.0,
        allowance_transport=300.0,
        allowance_meals=200.0,
        allowance_utilities=100.0,
        allowance_other=0.0,
        tax_rate_percent=15.0,
        pension_rate_percent=5.5,
        nssf_rate_percent=1.0,
        other_deduction=0.0,
        effective_from=datetime.utcnow(),
        is_active=True
    )


@pytest.fixture
def payroll_service(test_db):
    """Create PayrollService instance with test database"""
    return PayrollService(test_db)


# ================ Payroll Calculation Tests ================ 

class TestPayrollCalculations:
    """Test payroll calculation methods"""
    
    def test_calculate_allowances(self, payroll_service, sample_contract):
        """Test allowances calculation"""
        total, breakdown = payroll_service.calculate_allowances(sample_contract)
        
        # Verify total
        assert total == 1100.0  # 500 + 300 + 200 + 100
        
        # Verify breakdown
        assert breakdown["housing"] == 500.0
        assert breakdown["transport"] == 300.0
        assert breakdown["meals"] == 200.0
        assert breakdown["utilities"] == 100.0
        assert breakdown["other"] == 0.0
    
    def test_calculate_allowances_with_other(self, payroll_service, sample_contract):
        """Test allowances calculation with other allowance"""
        sample_contract.allowance_other = 250.0
        sample_contract.allowance_other_description = "Special allowance"
        
        total, breakdown = payroll_service.calculate_allowances(sample_contract)
        
        assert total == 1350.0  # 500 + 300 + 200 + 100 + 250
        assert breakdown["other"] == 250.0
    
    def test_calculate_gross_amount(self, payroll_service, sample_contract):
        """Test gross amount calculation (basic + allowances)"""
        gross, components = payroll_service.calculate_gross_amount(sample_contract)
        
        # 5000 (basic) + 1100 (allowances) = 6100
        assert gross == 6100.0
        assert components["basic_salary"] == 5000.0
        assert components["total_allowances"] == 1100.0
        assert components["gross_amount"] == 6100.0
    
    def test_calculate_tax(self, payroll_service):
        """Test tax calculation"""
        # 15% of 6100 = 915
        tax = payroll_service.calculate_tax(6100.0, 15.0)
        assert tax == 915.0
    
    def test_calculate_tax_zero_rate(self, payroll_service):
        """Test tax with zero rate"""
        tax = payroll_service.calculate_tax(6100.0, 0.0)
        assert tax == 0.0
    
    def test_calculate_tax_invalid_rate(self, payroll_service):
        """Test tax calculation with invalid rate"""
        with pytest.raises(PayrollCalculationError):
            payroll_service.calculate_tax(6100.0, 150.0)  # Invalid: > 100
        
        with pytest.raises(PayrollCalculationError):
            payroll_service.calculate_tax(6100.0, -5.0)  # Invalid: < 0
    
    def test_calculate_pension(self, payroll_service):
        """Test pension calculation"""
        # 5.5% of 6100 = 335.5
        pension = payroll_service.calculate_pension(6100.0, 5.5)
        assert pension == 335.5
    
    def test_calculate_nssf(self, payroll_service):
        """Test NSSF calculation"""
        # 1% of 6100 = 61
        nssf = payroll_service.calculate_nssf(6100.0, 1.0)
        assert nssf == 61.0
    
    def test_calculate_deductions(self, payroll_service, sample_contract):
        """Test total deductions calculation"""
        gross = 6100.0
        total, breakdown = payroll_service.calculate_deductions(gross, sample_contract)
        
        # 915 (tax) + 335.5 (pension) + 61 (nssf) + 0 (other)
        expected_total = 915.0 + 335.5 + 61.0
        assert abs(total - expected_total) < 0.01
        
        # Verify breakdown
        assert breakdown["tax"] == 915.0
        assert breakdown["pension"] == 335.5
        assert breakdown["nssf"] == 61.0
        assert breakdown["other"] == 0.0
    
    def test_calculate_deductions_with_other(self, payroll_service, sample_contract):
        """Test deductions with other deduction"""
        sample_contract.other_deduction = 150.0
        
        gross = 6100.0
        total, breakdown = payroll_service.calculate_deductions(gross, sample_contract)
        
        expected_total = 915.0 + 335.5 + 61.0 + 150.0
        assert abs(total - expected_total) < 0.01
        assert breakdown["other"] == 150.0
    
    def test_calculate_net_amount(self, payroll_service):
        """Test net amount calculation"""
        gross = 6100.0
        deductions = 1311.5
        
        net = payroll_service.calculate_net_amount(gross, deductions)
        
        # 6100 - 1311.5 = 4788.5
        assert abs(net - 4788.5) < 0.01
    
    def test_calculate_net_amount_never_negative(self, payroll_service):
        """Test net amount is never negative"""
        gross = 1000.0
        deductions = 5000.0  # Deductions > gross
        
        net = payroll_service.calculate_net_amount(gross, deductions)
        
        # Should return 0, not negative
        assert net == 0.0
    
    def test_calculate_payroll_for_staff(self, payroll_service, sample_contract):
        """Test complete payroll calculation for staff"""
        result = payroll_service.calculate_payroll_for_staff(sample_contract)
        
        # Verify all keys present
        assert "basic_salary" in result
        assert "total_allowances" in result
        assert "gross_amount" in result
        assert "tax_amount" in result
        assert "pension_amount" in result
        assert "nssf_amount" in result
        assert "total_deductions" in result
        assert "net_amount" in result
        assert "breakdown" in result
        
        # Verify calculations
        assert result["basic_salary"] == 5000.0
        assert result["total_allowances"] == 1100.0
        assert result["gross_amount"] == 6100.0
        assert result["tax_amount"] == 915.0
        assert abs(result["pension_amount"] - 335.5) < 0.01
        assert result["nssf_amount"] == 61.0
        
        # Net should be positive
        assert result["net_amount"] > 0
        assert result["final_net"] == result["net_amount"]  # No adjustments
    
    def test_calculate_payroll_with_adjustments(self, payroll_service, sample_contract):
        """Test payroll calculation with bonus adjustments"""
        adjustments = [
            {"adjustment_type": "bonus", "amount": 500.0},
            {"adjustment_type": "penalty", "amount": -100.0}
        ]
        
        result = payroll_service.calculate_payroll_for_staff(
            sample_contract, 
            adjustments
        )
        
        # Final net should include adjustments: net + 500 - 100 = net + 400
        expected_final_net = result["net_amount"] + 400.0
        assert abs(result["final_net"] - expected_final_net) < 0.01


# ================ Payroll Service Tests ================ 

class TestPayrollService:
    """Test PayrollService helper methods"""
    
    def test_get_period_name_valid_months(self, payroll_service):
        """Test period name generation for valid months"""
        assert payroll_service.get_period_name(2026, 1) == "January 2026"
        assert payroll_service.get_period_name(2026, 6) == "June 2026"
        assert payroll_service.get_period_name(2026, 12) == "December 2026"
    
    def test_get_period_name_invalid_months(self, payroll_service):
        """Test period name generation for invalid months"""
        result = payroll_service.get_period_name(2026, 13)
        assert "Period" in result or "Month" in result


# ================ Integration Tests ================ 

class TestPayrollIntegration:
    """Integration tests for payroll endpoints"""
    
    @pytest.mark.asyncio
    async def test_generate_payroll_run_no_staff(self, payroll_service, test_db):
        """Test payroll run generation with no active staff"""
        user = User(
            id="user-001",
            email="admin@test.edu.gh",
            password_hash="hash",
            first_name="Admin",
            last_name="User",
            role=UserRole.SCHOOL_ADMIN,
            school_id="test-school-001"
        )
        
        result = await payroll_service.generate_payroll_run(
            school_id="test-school-001",
            year=2026,
            month=1,
            current_user=user,
            notes="Test payroll"
        )
        
        assert result["success"] is False
        assert "No active staff" in result["message"]
    
    @pytest.mark.asyncio
    async def test_generate_payroll_run_invalid_month(self, payroll_service, test_db):
        """Test payroll run generation with invalid month"""
        user = User(
            id="user-001",
            email="admin@test.edu.gh",
            password_hash="hash",
            first_name="Admin",
            last_name="User",
            role=UserRole.SCHOOL_ADMIN,
            school_id="test-school-001"
        )
        
        result = await payroll_service.generate_payroll_run(
            school_id="test-school-001",
            year=2026,
            month=13,  # Invalid
            current_user=user
        )
        
        assert result["success"] is False
        assert "Invalid month" in result["message"]


# ================ Edge Cases Tests ================ 

class TestEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_high_gross_salary_calculation(self, payroll_service):
        """Test calculation with high gross salary"""
        contract = PayrollContract(
            id="high-salary",
            school_id="test-school",
            staff_id="test-staff",
            basic_salary=100000.0,
            allowance_housing=5000.0,
            allowance_transport=2000.0,
            allowance_meals=1000.0,
            allowance_utilities=500.0,
            tax_rate_percent=25.0,
            pension_rate_percent=10.0,
            nssf_rate_percent=2.0,
            effective_from=datetime.utcnow(),
            is_active=True
        )
        
        result = payroll_service.calculate_payroll_for_staff(contract)
        
        # Verify calculations work correctly
        assert result["basic_salary"] == 100000.0
        assert result["total_allowances"] == 8500.0
        assert result["gross_amount"] == 108500.0
        assert result["net_amount"] > 0
    
    def test_minimum_salary_calculation(self, payroll_service):
        """Test calculation with minimum salary"""
        contract = PayrollContract(
            id="min-salary",
            school_id="test-school",
            staff_id="test-staff",
            basic_salary=100.0,
            allowance_housing=0.0,
            allowance_transport=0.0,
            tax_rate_percent=0.0,
            pension_rate_percent=0.0,
            nssf_rate_percent=0.0,
            effective_from=datetime.utcnow(),
            is_active=True
        )
        
        result = payroll_service.calculate_payroll_for_staff(contract)
        
        assert result["gross_amount"] == 100.0
        assert result["total_deductions"] == 0.0
        assert result["net_amount"] == 100.0


# ================ Performance Tests ================ 

class TestPerformance:
    """Test performance with large datasets"""
    
    def test_bulk_calculation_performance(self, payroll_service):
        """Test that calculations are fast even with many staff"""
        contracts = []
        for i in range(100):
            contract = PayrollContract(
                id=f"contract-{i}",
                school_id="test-school",
                staff_id=f"staff-{i}",
                basic_salary=5000.0 + (i * 100),
                allowance_housing=500.0,
                allowance_transport=300.0,
                tax_rate_percent=15.0,
                pension_rate_percent=5.5,
                nssf_rate_percent=1.0,
                effective_from=datetime.utcnow(),
                is_active=True
            )
            contracts.append(contract)
        
        # Should calculate all in reasonable time
        import time
        start = time.time()
        
        for contract in contracts:
            payroll_service.calculate_payroll_for_staff(contract)
        
        elapsed = time.time() - start
        
        # All 100 calculations should complete in < 1 second
        assert elapsed < 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
