"""Integration tests for Student/Parent Assignment Endpoints

Tests:
1. Student Portal - Get my assignments
2. Student Portal - Submit assignment
3. Parent Portal - Get child's assignments
4. RBAC - Students can't access other students' assignments
5. RBAC - Parents can't access non-existent children
6. Status transitions (pending -> submitted -> graded)
"""

import requests
import json
from datetime import datetime
from colorama import Fore, Style, init

init(autoreset=True)

# Configuration
BASE_URL = "http://127.0.0.1:8000"
ADMIN_EMAIL = "admin@school.edu.gh"
ADMIN_PASSWORD = "admin123"

# Test credentials (from seed_data.py)
STUDENT_EMAIL = "student@school.edu.gh"
STUDENT_PASSWORD = "student123"
PARENT_EMAIL = "parent@school.edu.gh"
PARENT_PASSWORD = "parent123"
TEACHER_EMAIL = "teacher@school.edu.gh"
TEACHER_PASSWORD = "teacher123"

# Token storage
admin_token = None
student_token = None
parent_token = None
teacher_token = None

def print_test(test_name, passed, details=""):
    """Print test result with color"""
    status = f"{Fore.GREEN}✅ PASS{Style.RESET_ALL}" if passed else f"{Fore.RED}❌ FAIL{Style.RESET_ALL}"
    print(f"  {status} - {test_name}")
    if details and not passed:
        print(f"      {Fore.RED}{details}{Style.RESET_ALL}")


def print_section(section_name):
    """Print section header"""
    print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{section_name}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")


def login(email, password):
    """Login and return token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password}
    )
    
    if response.status_code == 200:
        data = response.json()
        return data.get("access_token")
    else:
        print(f"{Fore.RED}Login failed for {email}: {response.text}{Style.RESET_ALL}")
        return None


def test_connection():
    """Test backend connectivity"""
    print_section(f"{Fore.YELLOW}🔗 Testing Backend Connection{Style.RESET_ALL}")
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        if response.status_code < 400:
            print_test("Backend is running", True)
            return True
        else:
            print_test("Backend is running", False, f"Status: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print_test("Backend is running", False, f"Cannot connect to {BASE_URL}. Is the backend running?")
        return False


# ============================================================================
# TEST SUITE
# ============================================================================

def test_authentication():
    """Test login for all user types"""
    global admin_token, student_token, parent_token, teacher_token
    
    print_section("1️⃣  AUTHENTICATION")
    
    # Admin login
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    print_test("Admin login", admin_token is not None)
    
    # Student login
    student_token = login(STUDENT_EMAIL, STUDENT_PASSWORD)
    print_test("Student login", student_token is not None)
    
    # Parent login
    parent_token = login(PARENT_EMAIL, PARENT_PASSWORD)
    print_test("Parent login", parent_token is not None)
    
    # Teacher login
    teacher_token = login(TEACHER_EMAIL, TEACHER_PASSWORD)
    print_test("Teacher login", teacher_token is not None)


def test_student_get_assignments():
    """Test GET /api/student-portal/assignments/my-assignments"""
    print_section("2️⃣  STUDENT - GET ASSIGNMENTS")
    
    if not student_token:
        print(f"{Fore.RED}Skipped - No student token{Style.RESET_ALL}")
        return
    
    headers = {"Authorization": f"Bearer {student_token}"}
    response = requests.get(
        f"{BASE_URL}/api/student-portal/assignments/my-assignments",
        headers=headers
    )
    
    passed = response.status_code == 200
    print_test("Get student assignments", passed, response.text)
    
    if passed:
        data = response.json()
        assignments = data.get("assignments", [])
        print(f"  Found {Fore.YELLOW}{len(assignments)}{Style.RESET_ALL} assignments")
        
        # Verify response structure
        for assignment in assignments[:2]:  # Check first 2
            assert "id" in assignment, "Missing 'id' field"
            assert "title" in assignment, "Missing 'title' field"
            assert "subject_name" in assignment, "Missing 'subject_name' field"
            assert "teacher_name" in assignment, "Missing 'teacher_name' field"
            assert "due_date" in assignment, "Missing 'due_date' field"
            
            status_field = "submitted_at" in assignment or "graded" in assignment
            assert status_field, "Missing submission status fields"
        
        print(f"  {Fore.GREEN}Response structure verified{Style.RESET_ALL}")
        
        # Show sample assignment
        if assignments:
            sample = assignments[0]
            print(f"\n  📋 Sample Assignment:")
            print(f"     Title: {sample['title']}")
            print(f"     Subject: {sample['subject_name']}")
            print(f"     Teacher: {sample['teacher_name']}")
            print(f"     Type: {sample['assignment_type']}")
            print(f"     Due: {sample['due_date']}")
            if sample.get('graded'):
                print(f"     Score: {sample.get('score')}/{sample.get('max_score')}")


def test_student_submit_assignment():
    """Test POST /api/student-portal/assignments/{id}/submit"""
    print_section("3️⃣  STUDENT - SUBMIT ASSIGNMENT")
    
    if not student_token:
        print(f"{Fore.RED}Skipped - No student token{Style.RESET_ALL}")
        return
    
    # First get assignments
    headers = {"Authorization": f"Bearer {student_token}"}
    get_response = requests.get(
        f"{BASE_URL}/api/student-portal/assignments/my-assignments",
        headers=headers
    )
    
    if get_response.status_code != 200:
        print(f"{Fore.RED}Failed to get assignments{Style.RESET_ALL}")
        return
    
    assignments = get_response.json().get("assignments", [])
    if not assignments:
        print(f"{Fore.YELLOW}No assignments to submit{Style.RESET_ALL}")
        return
    
    # Try to submit first assignment
    assignment = assignments[0]
    assignment_id = assignment["id"]
    
    submit_response = requests.post(
        f"{BASE_URL}/api/student-portal/assignments/{assignment_id}/submit",
        headers=headers,
        json={"submission_text": "This is my submission for the assignment"}
    )
    
    passed = submit_response.status_code == 200
    print_test("Submit assignment", passed, submit_response.text)
    
    if passed:
        data = submit_response.json()
        print(f"  Submission ID: {Fore.YELLOW}{data.get('submission_id')}{Style.RESET_ALL}")
        print(f"  Status: {Fore.YELLOW}{data.get('status')}{Style.RESET_ALL}")
        print(f"  Submitted at: {data.get('submitted_at')}")


def test_parent_get_child_assignments():
    """Test GET /api/parent/child/{student_id}/assignments"""
    print_section("4️⃣  PARENT - GET CHILD'S ASSIGNMENTS")
    
    if not parent_token:
        print(f"{Fore.RED}Skipped - No parent token{Style.RESET_ALL}")
        return
    
    # Get parent's children first
    headers = {"Authorization": f"Bearer {parent_token}"}
    children_response = requests.get(
        f"{BASE_URL}/api/parent/children",
        headers=headers
    )
    
    passed = children_response.status_code == 200
    print_test("Get parent's children", passed, children_response.text)
    
    if not passed:
        return
    
    children = children_response.json()
    if not children:
        print(f"{Fore.YELLOW}No children linked to parent{Style.RESET_ALL}")
        return
    
    # Get assignments for first child
    child = children[0]
    child_id = child["id"]
    
    assignments_response = requests.get(
        f"{BASE_URL}/api/parent/child/{child_id}/assignments",
        headers=headers
    )
    
    passed = assignments_response.status_code == 200
    print_test("Get child's assignments", passed, assignments_response.text)
    
    if passed:
        data = assignments_response.json()
        assignments = data.get("assignments", [])
        print(f"  Found {Fore.YELLOW}{len(assignments)}{Style.RESET_ALL} assignments for {child['name']}")
        
        # Verify structure
        for assignment in assignments[:1]:
            assert "id" in assignment, "Missing 'id' field"
            assert "title" in assignment, "Missing 'title' field"
            assert "submission_status" in assignment, "Missing 'submission_status' field"
            assert "score" in assignment, "Missing 'score' field"
        
        print(f"  {Fore.GREEN}Response structure verified{Style.RESET_ALL}")
        
        # Show sample
        if assignments:
            sample = assignments[0]
            print(f"\n  📋 Sample Assignment for {child['name']}:")
            print(f"     Title: {sample['title']}")
            print(f"     Subject: {sample['subject_name']}")
            print(f"     Status: {sample.get('submission_status', 'pending')}")
            if sample.get('score'):
                print(f"     Score: {sample['score']}/{sample.get('max_score')}")


def test_rbac_student_isolation():
    """Test that students can't access other students' assignments"""
    print_section("5️⃣  RBAC - STUDENT ISOLATION")
    
    if not student_token:
        print(f"{Fore.RED}Skipped - No student token{Style.RESET_ALL}")
        return
    
    # Try with a fake student ID
    headers = {"Authorization": f"Bearer {student_token}"}
    fake_student_id = "fake-student-id-12345"
    
    response = requests.get(
        f"{BASE_URL}/api/parent/child/{fake_student_id}/assignments",
        headers=headers
    )
    
    # Should be 403 or 404
    passed = response.status_code in [403, 404]
    print_test(
        "Prevent access to other students",
        passed,
        f"Expected 403/404, got {response.status_code}"
    )


def test_rbac_parent_child_access():
    """Test that parents can only access their own children"""
    print_section("6️⃣  RBAC - PARENT-CHILD ISOLATION")
    
    if not parent_token:
        print(f"{Fore.RED}Skipped - No parent token{Style.RESET_ALL}")
        return
    
    headers = {"Authorization": f"Bearer {parent_token}"}
    fake_child_id = "fake-child-id-67890"
    
    response = requests.get(
        f"{BASE_URL}/api/parent/child/{fake_child_id}/assignments",
        headers=headers
    )
    
    # Should be 404
    passed = response.status_code == 404
    print_test(
        "Prevent access to unknown children",
        passed,
        f"Expected 404, got {response.status_code}"
    )


def test_assignment_status_variations():
    """Test that assignments show correct status"""
    print_section("7️⃣  ASSIGNMENT STATUS TRACKING")
    
    if not student_token:
        print(f"{Fore.RED}Skipped - No student token{Style.RESET_ALL}")
        return
    
    headers = {"Authorization": f"Bearer {student_token}"}
    response = requests.get(
        f"{BASE_URL}/api/student-portal/assignments/my-assignments",
        headers=headers
    )
    
    if response.status_code != 200:
        print(f"{Fore.RED}Failed to get assignments{Style.RESET_ALL}")
        return
    
    assignments = response.json().get("assignments", [])
    
    # Count statuses
    statuses = {}
    for assignment in assignments:
        if assignment.get("submitted_at"):
            if assignment.get("graded"):
                status = "graded"
            else:
                status = "submitted"
        else:
            status = "pending"
        statuses[status] = statuses.get(status, 0) + 1
    
    found_pending = statuses.get("pending", 0) > 0
    found_submitted = statuses.get("submitted", 0) > 0
    found_graded = statuses.get("graded", 0) > 0
    
    print_test("Found pending assignments", found_pending)
    print_test("Found submitted assignments", found_submitted)
    print_test("Found graded assignments", found_graded)
    
    print(f"\n  Status distribution:")
    for status, count in statuses.items():
        print(f"    - {status}: {count}")


def test_error_handling():
    """Test error cases"""
    print_section("8️⃣  ERROR HANDLING")
    
    # Missing token
    response = requests.get(f"{BASE_URL}/api/student-portal/assignments/my-assignments")
    passed = response.status_code == 403
    print_test("Missing token returns 403", passed)
    
    # Invalid token
    headers = {"Authorization": "Bearer invalid-token-12345"}
    response = requests.get(
        f"{BASE_URL}/api/student-portal/assignments/my-assignments",
        headers=headers
    )
    passed = response.status_code == 403
    print_test("Invalid token returns 403", passed)
    
    # Non-existent assignment
    if student_token:
        headers = {"Authorization": f"Bearer {student_token}"}
        response = requests.post(
            f"{BASE_URL}/api/student-portal/assignments/fake-id/submit",
            headers=headers,
            json={"submission_text": "test"}
        )
        passed = response.status_code == 404
        print_test("Non-existent assignment returns 404", passed)


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Run all tests"""
    print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}ASSIGNMENT ENDPOINTS - INTEGRATION TEST SUITE{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Base URL: {BASE_URL}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    
    try:
        # Test connection first
        if not test_connection():
            print(f"\n{Fore.RED}Cannot proceed without backend connection{Style.RESET_ALL}")
            return
        
        test_authentication()
        test_student_get_assignments()
        test_student_submit_assignment()
        test_parent_get_child_assignments()
        test_rbac_student_isolation()
        test_rbac_parent_child_access()
        test_assignment_status_variations()
        test_error_handling()
        
        print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}✅ TEST SUITE COMPLETE{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")
        
    except Exception as e:
        print(f"\n{Fore.RED}❌ ERROR: {str(e)}{Style.RESET_ALL}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
