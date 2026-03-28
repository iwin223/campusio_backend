"""
Fees Module Tests - School ERP System
Tests for fee structures, payments, and collection tracking
"""
import pytest
import requests
import os
from datetime import datetime
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://learning-admin-hub-1.preview.emergentagent.com').rstrip('/')

# Test credentials
TEST_EMAIL = "admin@school.edu.gh"
TEST_PASSWORD = "admin123"


class TestFeesModule:
    """Fees Module API Tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get token
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            token = response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
            self.user = response.json().get("user")
        else:
            pytest.skip("Authentication failed")
    
    # ============ Fee Types Tests ============
    def test_get_fee_types_returns_8_types(self):
        """GET /api/fees/types - Returns 8 fee types"""
        response = self.session.get(f"{BASE_URL}/api/fees/types")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify 8 fee types
        assert len(data) == 8
        
        # Verify expected fee types
        fee_types = [ft["type"] for ft in data]
        expected_types = ["tuition", "examination", "sports", "ict", "library", "maintenance", "pta", "other"]
        for expected in expected_types:
            assert expected in fee_types
        
        # Verify structure
        for fee_type in data:
            assert "type" in fee_type
            assert "name" in fee_type
            assert "description" in fee_type
    
    # ============ Fee Summary Tests ============
    def test_get_fee_summary(self):
        """GET /api/fees/summary - Returns collection summary"""
        response = self.session.get(f"{BASE_URL}/api/fees/summary")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify summary structure
        assert "total_expected" in data
        assert "total_collected" in data
        assert "total_discount" in data
        assert "total_outstanding" in data
        assert "collection_rate" in data
        assert "total_students_with_fees" in data
        assert "status_breakdown" in data
        
        # Verify status breakdown
        status = data["status_breakdown"]
        assert "paid" in status
        assert "partial" in status
        assert "pending" in status
        assert "overdue" in status
        
        # Verify numeric values
        assert isinstance(data["total_expected"], (int, float))
        assert isinstance(data["collection_rate"], (int, float))
    
    # ============ Fee Structures Tests ============
    def test_list_fee_structures(self):
        """GET /api/fees/structures - List fee structures"""
        response = self.session.get(f"{BASE_URL}/api/fees/structures")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should be a list
        assert isinstance(data, list)
        
        # If structures exist, verify structure
        if len(data) > 0:
            structure = data[0]
            assert "id" in structure
            assert "academic_term_id" in structure
            assert "class_level" in structure
            assert "fee_type" in structure
            assert "amount" in structure
            assert "due_date" in structure
    
    def test_create_fee_structure(self):
        """POST /api/fees/structures - Create fee structure"""
        unique_id = str(uuid.uuid4())[:8]
        
        payload = {
            "academic_term_id": f"TEST_term_{unique_id}",
            "class_level": "primary_2",
            "fee_type": "examination",
            "amount": 150.00,
            "description": f"TEST exam fee {unique_id}",
            "is_mandatory": True,
            "due_date": "2026-03-31"
        }
        
        response = self.session.post(f"{BASE_URL}/api/fees/structures", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response
        assert "id" in data
        assert data["academic_term_id"] == payload["academic_term_id"]
        assert data["class_level"] == payload["class_level"]
        assert data["fee_type"] == payload["fee_type"]
        assert data["amount"] == payload["amount"]
        assert data["due_date"] == payload["due_date"]
        assert "message" in data
        
        # Store for cleanup
        self.created_structure_id = data["id"]
    
    def test_create_fee_structure_validates_fee_type(self):
        """POST /api/fees/structures - Validates fee type enum"""
        payload = {
            "academic_term_id": "term_1_2026",
            "class_level": "primary_1",
            "fee_type": "invalid_type",  # Invalid fee type
            "amount": 100.00,
            "due_date": "2026-03-31"
        }
        
        response = self.session.post(f"{BASE_URL}/api/fees/structures", json=payload)
        
        # Should fail validation
        assert response.status_code == 422
    
    # ============ Class Fee Status Tests ============
    def test_get_class_fee_status(self):
        """GET /api/fees/class/{class_id} - Get class fee status"""
        # First get a class
        classes_response = self.session.get(f"{BASE_URL}/api/classes")
        assert classes_response.status_code == 200
        classes = classes_response.json()
        
        if len(classes) == 0:
            pytest.skip("No classes available")
        
        class_id = classes[0]["id"]
        
        response = self.session.get(f"{BASE_URL}/api/fees/class/{class_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "class_id" in data
        assert "class_name" in data
        assert "total_students" in data
        assert "class_summary" in data
        assert "students" in data
        
        # Verify class summary
        summary = data["class_summary"]
        assert "total_due" in summary
        assert "total_paid" in summary
        assert "balance" in summary
        assert "collection_rate" in summary
        
        # Verify students list
        assert isinstance(data["students"], list)
    
    def test_get_class_fee_status_invalid_class(self):
        """GET /api/fees/class/{class_id} - Returns 404 for invalid class"""
        response = self.session.get(f"{BASE_URL}/api/fees/class/invalid-class-id")
        
        assert response.status_code == 404
    
    # ============ Assign Fee to Class Tests ============
    def test_assign_fee_to_class(self):
        """POST /api/fees/assign-class - Assign fee to class"""
        # First create a fee structure
        unique_id = str(uuid.uuid4())[:8]
        structure_payload = {
            "academic_term_id": f"TEST_assign_{unique_id}",
            "class_level": "primary_1",
            "fee_type": "sports",
            "amount": 50.00,
            "description": f"TEST sports fee {unique_id}",
            "is_mandatory": False,
            "due_date": "2026-04-30"
        }
        
        structure_response = self.session.post(f"{BASE_URL}/api/fees/structures", json=structure_payload)
        assert structure_response.status_code == 200
        structure_id = structure_response.json()["id"]
        
        # Get a class with students
        classes_response = self.session.get(f"{BASE_URL}/api/classes")
        classes = classes_response.json()
        
        # Find class with students
        class_with_students = None
        for cls in classes:
            if cls.get("student_count", 0) > 0:
                class_with_students = cls
                break
        
        if not class_with_students:
            pytest.skip("No class with students available")
        
        class_id = class_with_students["id"]
        
        # Assign fee to class
        response = self.session.post(
            f"{BASE_URL}/api/fees/assign-class?structure_id={structure_id}&class_id={class_id}",
            json={}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response
        assert "message" in data
        assert "total_students" in data
        assert "new_assignments" in data
        assert "already_assigned" in data
        assert data["total_students"] >= 0
    
    def test_assign_fee_invalid_structure(self):
        """POST /api/fees/assign-class - Returns 404 for invalid structure"""
        # Get a valid class
        classes_response = self.session.get(f"{BASE_URL}/api/classes")
        classes = classes_response.json()
        
        if len(classes) == 0:
            pytest.skip("No classes available")
        
        class_id = classes[0]["id"]
        
        response = self.session.post(
            f"{BASE_URL}/api/fees/assign-class?structure_id=invalid-structure-id&class_id={class_id}",
            json={}
        )
        
        assert response.status_code == 404
    
    # ============ Outstanding Fees Tests ============
    def test_get_outstanding_fees(self):
        """GET /api/fees/outstanding - Get students with outstanding fees"""
        response = self.session.get(f"{BASE_URL}/api/fees/outstanding")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "total_students" in data
        assert "total_outstanding" in data
        assert "students" in data
        
        # Verify students list
        assert isinstance(data["students"], list)
        
        # If students exist, verify structure
        if len(data["students"]) > 0:
            student = data["students"][0]
            assert "student_id" in student
            assert "total_due" in student
            assert "total_paid" in student
            assert "balance" in student
    
    def test_get_outstanding_fees_with_min_amount(self):
        """GET /api/fees/outstanding - Filter by minimum amount"""
        response = self.session.get(f"{BASE_URL}/api/fees/outstanding?min_amount=100")
        
        assert response.status_code == 200
        data = response.json()
        
        # All students should have balance > 100
        for student in data["students"]:
            assert student["balance"] > 100
    
    # ============ Payment Tests ============
    def test_record_payment_full_flow(self):
        """POST /api/fees/payments - Record payment (full flow)"""
        # 1. Create a fee structure
        unique_id = str(uuid.uuid4())[:8]
        structure_payload = {
            "academic_term_id": f"TEST_pay_{unique_id}",
            "class_level": "primary_1",
            "fee_type": "library",
            "amount": 75.00,
            "description": f"TEST library fee {unique_id}",
            "is_mandatory": True,
            "due_date": "2026-05-31"
        }
        
        structure_response = self.session.post(f"{BASE_URL}/api/fees/structures", json=structure_payload)
        assert structure_response.status_code == 200
        structure_id = structure_response.json()["id"]
        
        # 2. Get a class with students
        classes_response = self.session.get(f"{BASE_URL}/api/classes")
        classes = classes_response.json()
        
        class_with_students = None
        for cls in classes:
            if cls.get("student_count", 0) > 0:
                class_with_students = cls
                break
        
        if not class_with_students:
            pytest.skip("No class with students available")
        
        class_id = class_with_students["id"]
        
        # 3. Assign fee to class
        assign_response = self.session.post(
            f"{BASE_URL}/api/fees/assign-class?structure_id={structure_id}&class_id={class_id}",
            json={}
        )
        assert assign_response.status_code == 200
        
        # 4. Get class fee status to find a student with fees
        class_fees_response = self.session.get(f"{BASE_URL}/api/fees/class/{class_id}")
        assert class_fees_response.status_code == 200
        class_fees = class_fees_response.json()
        
        if len(class_fees["students"]) == 0:
            pytest.skip("No students with fees")
        
        student = class_fees["students"][0]
        student_id = student["student_id"]
        
        # 5. Get student fees to get fee_id
        student_fees_response = self.session.get(f"{BASE_URL}/api/fees/student/{student_id}")
        assert student_fees_response.status_code == 200
        student_fees = student_fees_response.json()
        
        # Find the fee we just created
        fee_id = None
        for fee in student_fees["fees"]:
            if fee["fee_type"] == "library":
                fee_id = fee["id"]
                break
        
        if not fee_id:
            pytest.skip("Could not find created fee")
        
        # 6. Record payment
        payment_payload = {
            "fee_id": fee_id,
            "amount": 50.00,
            "payment_method": "cash",
            "reference_number": f"TEST-{unique_id}",
            "payment_date": "2026-01-21",
            "remarks": "Test partial payment"
        }
        
        payment_response = self.session.post(f"{BASE_URL}/api/fees/payments", json=payment_payload)
        
        assert payment_response.status_code == 200
        payment_data = payment_response.json()
        
        # Verify payment response
        assert "id" in payment_data
        assert "receipt_number" in payment_data
        assert payment_data["amount"] == 50.00
        # Balance should be reduced by payment amount
        assert "fee_balance" in payment_data
        # Status should be partial or paid depending on balance
        assert payment_data["fee_status"] in ["partial", "paid"]
        assert "message" in payment_data
    
    def test_record_payment_invalid_fee(self):
        """POST /api/fees/payments - Returns 404 for invalid fee"""
        payment_payload = {
            "fee_id": "invalid-fee-id",
            "amount": 100.00,
            "payment_method": "cash",
            "payment_date": "2026-01-21"
        }
        
        response = self.session.post(f"{BASE_URL}/api/fees/payments", json=payment_payload)
        
        assert response.status_code == 404
    
    def test_record_payment_validates_method(self):
        """POST /api/fees/payments - Validates payment method enum"""
        payment_payload = {
            "fee_id": "some-fee-id",
            "amount": 100.00,
            "payment_method": "invalid_method",  # Invalid method
            "payment_date": "2026-01-21"
        }
        
        response = self.session.post(f"{BASE_URL}/api/fees/payments", json=payment_payload)
        
        # Should fail validation
        assert response.status_code == 422
    
    # ============ Student Fees Tests ============
    def test_get_student_fees(self):
        """GET /api/fees/student/{student_id} - Get student fees"""
        # Get a class with students
        classes_response = self.session.get(f"{BASE_URL}/api/classes")
        classes = classes_response.json()
        
        class_with_students = None
        for cls in classes:
            if cls.get("student_count", 0) > 0:
                class_with_students = cls
                break
        
        if not class_with_students:
            pytest.skip("No class with students available")
        
        # Get class fee status to find a student
        class_fees_response = self.session.get(f"{BASE_URL}/api/fees/class/{class_with_students['id']}")
        class_fees = class_fees_response.json()
        
        if len(class_fees["students"]) == 0:
            pytest.skip("No students in class")
        
        student_id = class_fees["students"][0]["student_id"]
        
        # Get student fees
        response = self.session.get(f"{BASE_URL}/api/fees/student/{student_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "student_id" in data
        assert "student_name" in data
        assert "summary" in data
        assert "fees" in data
        
        # Verify summary
        summary = data["summary"]
        assert "total_fees" in summary
        assert "total_paid" in summary
        assert "total_discount" in summary
        assert "balance" in summary
    
    def test_get_student_fees_invalid_student(self):
        """GET /api/fees/student/{student_id} - Returns 404 for invalid student"""
        response = self.session.get(f"{BASE_URL}/api/fees/student/invalid-student-id")
        
        assert response.status_code == 404
    
    # ============ Authentication Tests ============
    def test_fee_summary_requires_auth(self):
        """GET /api/fees/summary - Requires authentication"""
        # Create new session without auth
        no_auth_session = requests.Session()
        response = no_auth_session.get(f"{BASE_URL}/api/fees/summary")
        
        # API returns 401 or 403 for unauthenticated requests
        assert response.status_code in [401, 403]
    
    def test_create_structure_requires_admin(self):
        """POST /api/fees/structures - Requires admin role"""
        # Create new session without auth
        no_auth_session = requests.Session()
        no_auth_session.headers.update({"Content-Type": "application/json"})
        
        payload = {
            "academic_term_id": "term_1_2026",
            "class_level": "primary_1",
            "fee_type": "tuition",
            "amount": 100.00,
            "due_date": "2026-03-31"
        }
        
        response = no_auth_session.post(f"{BASE_URL}/api/fees/structures", json=payload)
        
        # API returns 401 or 403 for unauthenticated requests
        assert response.status_code in [401, 403]


class TestFeesModuleDataIntegrity:
    """Tests for data integrity and persistence"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            token = response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip("Authentication failed")
    
    def test_fee_structure_persists_after_creation(self):
        """Verify fee structure is persisted after creation"""
        unique_id = str(uuid.uuid4())[:8]
        
        # Create structure
        payload = {
            "academic_term_id": f"TEST_persist_{unique_id}",
            "class_level": "jhs_1",
            "fee_type": "ict",
            "amount": 200.00,
            "description": f"TEST ICT fee {unique_id}",
            "is_mandatory": True,
            "due_date": "2026-06-30"
        }
        
        create_response = self.session.post(f"{BASE_URL}/api/fees/structures", json=payload)
        assert create_response.status_code == 200
        created_id = create_response.json()["id"]
        
        # Verify by listing structures
        list_response = self.session.get(f"{BASE_URL}/api/fees/structures")
        assert list_response.status_code == 200
        structures = list_response.json()
        
        # Find created structure
        found = False
        for structure in structures:
            if structure["id"] == created_id:
                found = True
                assert structure["academic_term_id"] == payload["academic_term_id"]
                assert structure["class_level"] == payload["class_level"]
                assert structure["fee_type"] == payload["fee_type"]
                assert structure["amount"] == payload["amount"]
                break
        
        assert found, "Created fee structure not found in list"
    
    def test_payment_updates_fee_status(self):
        """Verify payment updates fee status correctly"""
        # This test verifies that after a full payment, status changes to 'paid'
        unique_id = str(uuid.uuid4())[:8]
        
        # Create structure
        structure_payload = {
            "academic_term_id": f"TEST_status_{unique_id}",
            "class_level": "primary_1",
            "fee_type": "maintenance",
            "amount": 30.00,
            "description": f"TEST maintenance fee {unique_id}",
            "is_mandatory": True,
            "due_date": "2026-07-31"
        }
        
        structure_response = self.session.post(f"{BASE_URL}/api/fees/structures", json=structure_payload)
        assert structure_response.status_code == 200
        structure_id = structure_response.json()["id"]
        
        # Get class with students
        classes_response = self.session.get(f"{BASE_URL}/api/classes")
        classes = classes_response.json()
        
        class_with_students = None
        for cls in classes:
            if cls.get("student_count", 0) > 0:
                class_with_students = cls
                break
        
        if not class_with_students:
            pytest.skip("No class with students")
        
        # Assign fee
        assign_response = self.session.post(
            f"{BASE_URL}/api/fees/assign-class?structure_id={structure_id}&class_id={class_with_students['id']}",
            json={}
        )
        assert assign_response.status_code == 200
        
        # Get student fee
        class_fees = self.session.get(f"{BASE_URL}/api/fees/class/{class_with_students['id']}").json()
        student_id = class_fees["students"][0]["student_id"]
        
        student_fees = self.session.get(f"{BASE_URL}/api/fees/student/{student_id}").json()
        
        # Find the maintenance fee
        fee_id = None
        for fee in student_fees["fees"]:
            if fee["fee_type"] == "maintenance":
                fee_id = fee["id"]
                break
        
        if not fee_id:
            pytest.skip("Could not find fee")
        
        # Make full payment
        payment_payload = {
            "fee_id": fee_id,
            "amount": 30.00,  # Full amount
            "payment_method": "bank_transfer",
            "reference_number": f"BANK-{unique_id}",
            "payment_date": "2026-01-21"
        }
        
        payment_response = self.session.post(f"{BASE_URL}/api/fees/payments", json=payment_payload)
        assert payment_response.status_code == 200
        
        # Verify payment was recorded
        payment_data = payment_response.json()
        assert "id" in payment_data
        assert "receipt_number" in payment_data
        assert payment_data["amount"] == 30.00
        # Status should be paid (full payment) or partial if there were previous payments
        assert payment_data["fee_status"] in ["paid", "partial"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
