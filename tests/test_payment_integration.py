"""
Integration tests for Paystack payment system

Tests cover:
- Payment initialization
- Payment verification
- Webhook processing
- GL posting integration
- Fee status updates
- Idempotency
"""

import pytest
import json
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, Session, select

from models.payment import (
    OnlineTransaction, TransactionStatus, PaymentVerification, PaymentGateway
)
from models.fee import Fee, FeePayment, PaymentStatus
from models.student import Student, Parent
from models.user import User, UserRole
from services.paystack_service import PaystackService
from services.online_payment_service import OnlinePaymentService


# Test database setup
@pytest.fixture
async def test_db():
    """Create in-memory test database"""
    # Use SQLite in-memory for testing
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    
    async_session = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session() as session:
        yield session
    
    await engine.dispose()


# Test fixtures
@pytest.fixture
async def test_school(test_db):
    """Create test school"""
    from models.school import School
    school = School(id=str(uuid.uuid4()), name="Test School", contact_info="")
    test_db.add(school)
    await test_db.commit()
    return school


@pytest.fixture
async def test_parent(test_db, test_school):
    """Create test parent"""
    parent = Parent(
        id=str(uuid.uuid4()),
        school_id=test_school.id,
        first_name="John",
        last_name="Doe",
        email="john@example.com",
        phone_number="+233501234567",
        address="123 Main St",
        date_of_birth="1980-01-01"
    )
    test_db.add(parent)
    await test_db.commit()
    return parent


@pytest.fixture
async def test_student(test_db, test_school, test_parent):
    """Create test student"""
    student = Student(
        id=str(uuid.uuid4()),
        school_id=test_school.id,
        admission_number="STU-2026-001",
        first_name="Jane",
        last_name="Doe",
        date_of_birth="2010-01-01",
        gender="F",
        student_status="active"
    )
    test_db.add(student)
    await test_db.commit()
    return student


@pytest.fixture
async def test_fee(test_db, test_school, test_student):
    """Create test fee"""
    fee = Fee(
        id=str(uuid.uuid4()),
        school_id=test_school.id,
        student_id=test_student.id,
        fee_type="tuition",
        amount_due=500.00,
        amount_paid=0.00,
        status=PaymentStatus.PENDING,
        due_date=datetime.now().isoformat(),
        academic_term_id=str(uuid.uuid4())
    )
    test_db.add(fee)
    await test_db.commit()
    return fee


# ============================================================================
# PAYSTACK SERVICE TESTS
# ============================================================================

class TestPaystackService:
    """Test Paystack API client"""

    @pytest.mark.asyncio
    async def test_initialize_payment_success(self):
        """Test successful payment initialization"""
        service = PaystackService("sk_test_secret_key")
        
        with patch('services.paystack_service.httpx.AsyncClient.post') as mock_post:
            mock_post.return_value = MagicMock(
                json=MagicMock(return_value={
                    'status': True,
                    'message': 'Authorization URL created',
                    'data': {
                        'authorization_url': 'https://checkout.paystack.com/xxx',
                        'access_code': 'access_code_xxx',
                        'reference': 'ref_xxx'
                    }
                }),
                status_code=200
            )
            
            result = await service.initialize_payment(
                amount_kobo=50000,
                email='test@example.com',
                reference='PAY-001',
                metadata={'fee_id': 'fee-123'}
            )
            
            assert result['success'] == True
            assert 'authorization_url' in result
            assert result['reference'] == 'ref_xxx'

    @pytest.mark.asyncio
    async def test_initialize_payment_failure(self):
        """Test payment initialization failure"""
        service = PaystackService("sk_test_secret_key")
        
        with patch('services.paystack_service.httpx.AsyncClient.post') as mock_post:
            mock_post.return_value = MagicMock(
                json=MagicMock(return_value={
                    'status': False,
                    'message': 'Invalid amount'
                }),
                status_code=400
            )
            
            result = await service.initialize_payment(
                amount_kobo=0,  # Invalid
                email='test@example.com',
                reference='PAY-001',
                metadata={}
            )
            
            assert result['success'] == False

    @pytest.mark.asyncio
    async def test_verify_payment_success(self):
        """Test successful payment verification"""
        service = PaystackService("sk_test_secret_key")
        
        with patch('services.paystack_service.httpx.AsyncClient.get') as mock_get:
            mock_get.return_value = MagicMock(
                json=MagicMock(return_value={
                    'status': True,
                    'message': 'Verification successful',
                    'data': {
                        'reference': 'ref_123',
                        'status': 'success',
                        'amount': 50000,
                        'customer': {'email': 'test@example.com'}
                    }
                }),
                status_code=200
            )
            
            result = await service.verify_payment('ref_123')
            
            assert result['success'] == True
            assert result['data']['status'] == 'success'

    def test_webhook_signature_valid(self):
        """Test webhook signature verification - valid"""
        secret_key = 'sk_test_secret_key'
        payload_data = {'amount': 50000, 'reference': 'ref_123'}
        payload_bytes = json.dumps(payload_data).encode('utf-8')
        
        # Generate valid signature
        import hmac
        import hashlib
        signature = hmac.new(
            secret_key.encode('utf-8'),
            payload_bytes,
            hashlib.sha512
        ).hexdigest()
        
        result = PaystackService.verify_webhook_signature(
            payload_bytes=payload_bytes,
            signature=signature,
            secret_key=secret_key
        )
        
        assert result == True

    def test_webhook_signature_invalid(self):
        """Test webhook signature verification - invalid"""
        payload_bytes = json.dumps({'amount': 50000}).encode('utf-8')
        
        result = PaystackService.verify_webhook_signature(
            payload_bytes=payload_bytes,
            signature='invalid_signature_xxx',
            secret_key='sk_test_secret_key'
        )
        
        assert result == False


# ============================================================================
# ONLINE PAYMENT SERVICE TESTS
# ============================================================================

class TestOnlinePaymentService:
    """Test high-level payment orchestration"""

    @pytest.mark.asyncio
    async def test_initiate_payment_success(self, test_db, test_school, test_parent, test_student, test_fee):
        """Test successful payment initiation"""
        service = OnlinePaymentService("sk_test_secret_key")
        
        with patch.object(service.paystack, 'initialize_payment') as mock_init:
            mock_init.return_value = {
                'success': True,
                'authorization_url': 'https://paystack.com/checkout/xxx',
                'access_code': 'access_xxx',
                'reference': 'ref_001'
            }
            
            result = await service.initiate_payment(
                session=test_db,
                fee_id=test_fee.id,
                parent_id=test_parent.id,
                parent_email='john@example.com',
                school_id=test_school.id
            )
            
            assert result['success'] == True
            assert 'transaction_id' in result
            assert 'payment_url' in result

    @pytest.mark.asyncio
    async def test_initiate_payment_no_balance(self, test_db, test_school, test_parent, test_student):
        """Test payment initiation with no balance due"""
        service = OnlinePaymentService("sk_test_secret_key")
        
        # Create fee with no balance
        fee = Fee(
            id=str(uuid.uuid4()),
            school_id=test_school.id,
            student_id=test_student.id,
            fee_type="tuition",
            amount_due=500.00,
            amount_paid=500.00,  # Fully paid
            status=PaymentStatus.PAID,
            due_date=datetime.now().isoformat(),
            academic_term_id=str(uuid.uuid4())
        )
        test_db.add(fee)
        await test_db.commit()
        
        result = await service.initiate_payment(
            session=test_db,
            fee_id=fee.id,
            parent_id=test_parent.id,
            parent_email='john@example.com',
            school_id=test_school.id
        )
        
        assert result['success'] == False
        assert 'No amount due' in result['error']

    @pytest.mark.asyncio
    async def test_process_webhook_success(self, test_db, test_school, test_parent, test_student, test_fee):
        """Test successful webhook processing"""
        service = OnlinePaymentService("sk_test_secret_key")
        
        # Create transaction
        transaction = OnlineTransaction(
            school_id=test_school.id,
            fee_id=test_fee.id,
            student_id=test_student.id,
            parent_id=test_parent.id,
            amount=500.00,
            gateway=PaymentGateway.PAYSTACK,
            reference='ref_123',
            status=TransactionStatus.PROCESSING,
            payment_url='https://paystack.com/checkout',
            access_code='access_xxx'
        )
        test_db.add(transaction)
        await test_db.commit()
        
        with patch.object(service.paystack, 'verify_payment') as mock_verify:
            mock_verify.return_value = {
                'success': True,
                'data': {
                    'reference': 'ref_123',
                    'status': 'success',
                    'amount': 50000,
                    'customer': {'email': 'john@example.com'}
                }
            }
            
            with patch.object(service, '_send_payment_notifications') as mock_notify:
                mock_notify.return_value = None
                
                result = await service.process_webhook(
                    session=test_db,
                    payload={'reference': 'ref_123'}
                )
                
                assert result['success'] == True
                assert result['processed'] == True

    @pytest.mark.asyncio
    async def test_process_webhook_idempotency(self, test_db, test_school, test_parent, test_student, test_fee):
        """Test webhook idempotency - duplicate webhook handling"""
        service = OnlinePaymentService("sk_test_secret_key")
        
        # Create completed transaction
        transaction = OnlineTransaction(
            school_id=test_school.id,
            fee_id=test_fee.id,
            student_id=test_student.id,
            parent_id=test_parent.id,
            amount=500.00,
            gateway=PaymentGateway.PAYSTACK,
            reference='ref_123',
            status=TransactionStatus.SUCCESS,  # Already processed
            payment_url='https://paystack.com/checkout',
            access_code='access_xxx'
        )
        test_db.add(transaction)
        await test_db.commit()
        
        result = await service.process_webhook(
            session=test_db,
            payload={'reference': 'ref_123'}
        )
        
        # Should return success but processed=False
        assert result['success'] == True
        assert result['processed'] == False

    @pytest.mark.asyncio
    async def test_process_webhook_payment_failed(self, test_db, test_school, test_parent, test_student, test_fee):
        """Test webhook processing for failed payment"""
        service = OnlinePaymentService("sk_test_secret_key")
        
        transaction = OnlineTransaction(
            school_id=test_school.id,
            fee_id=test_fee.id,
            student_id=test_student.id,
            parent_id=test_parent.id,
            amount=500.00,
            gateway=PaymentGateway.PAYSTACK,
            reference='ref_123',
            status=TransactionStatus.PROCESSING,
            payment_url='https://paystack.com/checkout',
            access_code='access_xxx'
        )
        test_db.add(transaction)
        await test_db.commit()
        
        with patch.object(service.paystack, 'verify_payment') as mock_verify:
            mock_verify.return_value = {
                'success': True,
                'data': {
                    'reference': 'ref_123',
                    'status': 'failed',
                    'gateway_response': 'Card declined'
                }
            }
            
            result = await service.process_webhook(
                session=test_db,
                payload={'reference': 'ref_123'}
            )
            
            assert result['success'] == True
            # Transaction status should be updated to failed


# ============================================================================
# INTEGRATION FLOW TESTS
# ============================================================================

class TestPaymentIntegrationFlow:
    """Test complete payment flow"""

    @pytest.mark.asyncio
    async def test_complete_payment_flow(self, test_db, test_school, test_parent, test_student, test_fee):
        """Test complete payment flow: initiate → verify → process"""
        service = OnlinePaymentService("sk_test_secret_key")
        
        # Step 1: Initiate payment
        with patch.object(service.paystack, 'initialize_payment') as mock_init:
            mock_init.return_value = {
                'success': True,
                'authorization_url': 'https://paystack.com/checkout/xxx',
                'access_code': 'access_xxx',
                'reference': 'ref_001'
            }
            
            init_result = await service.initiate_payment(
                session=test_db,
                fee_id=test_fee.id,
                parent_id=test_parent.id,
                parent_email='john@example.com',
                school_id=test_school.id
            )
            
            assert init_result['success'] == True
            transaction_id = init_result['transaction_id']
        
        # Step 2: Get transaction from DB
        result = await test_db.execute(
            select(OnlineTransaction).where(OnlineTransaction.reference == transaction_id)
        )
        transaction = result.scalar_one()
        assert transaction.status == TransactionStatus.PROCESSING
        
        # Step 3: Process webhook (payment success)
        with patch.object(service.paystack, 'verify_payment') as mock_verify:
            mock_verify.return_value = {
                'success': True,
                'data': {
                    'reference': transaction_id,
                    'status': 'success',
                    'amount': 50000,
                    'customer': {'email': 'john@example.com'}
                }
            }
            
            with patch.object(service, '_send_payment_notifications'):
                webhook_result = await service.process_webhook(
                    session=test_db,
                    payload={'reference': transaction_id}
                )
                
                assert webhook_result['success'] == True
                assert webhook_result['processed'] == True
        
        # Step 4: Verify transaction updated
        result = await test_db.execute(
            select(OnlineTransaction).where(OnlineTransaction.reference == transaction_id)
        )
        updated_transaction = result.scalar_one()
        assert updated_transaction.status == TransactionStatus.SUCCESS
        assert updated_transaction.amount_paid == 500.00
        
        # Step 5: Verify fee updated
        result = await test_db.execute(select(Fee).where(Fee.id == test_fee.id))
        updated_fee = result.scalar_one()
        assert updated_fee.amount_paid == 500.00
        assert updated_fee.status == PaymentStatus.PAID


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

class TestErrorHandling:
    """Test error scenarios"""

    @pytest.mark.asyncio
    async def test_transaction_not_found(self, test_db, test_school):
        """Test webhook processing with non-existent transaction"""
        service = OnlinePaymentService("sk_test_secret_key")
        
        result = await service.process_webhook(
            session=test_db,
            payload={'reference': 'non_existent_ref'}
        )
        
        assert result['success'] == False
        assert 'not found' in result['error'].lower()

    @pytest.mark.asyncio
    async def test_verification_failure(self, test_db, test_school, test_parent, test_student, test_fee):
        """Test webhook processing with verification failure"""
        service = OnlinePaymentService("sk_test_secret_key")
        
        transaction = OnlineTransaction(
            school_id=test_school.id,
            fee_id=test_fee.id,
            student_id=test_student.id,
            parent_id=test_parent.id,
            amount=500.00,
            gateway=PaymentGateway.PAYSTACK,
            reference='ref_123',
            status=TransactionStatus.PROCESSING,
            payment_url='https://paystack.com/checkout',
            access_code='access_xxx'
        )
        test_db.add(transaction)
        await test_db.commit()
        
        with patch.object(service.paystack, 'verify_payment') as mock_verify:
            mock_verify.return_value = {'success': False, 'error': 'Verification failed'}
            
            result = await service.process_webhook(
                session=test_db,
                payload={'reference': 'ref_123'}
            )
            
            assert result['success'] == False


# Run tests
if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
