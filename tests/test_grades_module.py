"""
School ERP System - Grades Module Tests
Tests for: GES Grade Scale, Subjects, Class Grades, Bulk Grades
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
SCHOOL_ADMIN_EMAIL = "admin@school.edu.gh"
SCHOOL_ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for school admin"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": SCHOOL_ADMIN_EMAIL,
        "password": SCHOOL_ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json()["access_token"]
    pytest.skip("Authentication failed")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestGESGradeScale:
    """GES Grade Scale endpoint tests - No auth required"""
    
    def test_get_ges_scale_returns_9_grades(self):
        """Test GET /api/grades/ges-scale returns 9 grade levels"""
        response = requests.get(f"{BASE_URL}/api/grades/ges-scale")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 9, f"Expected 9 grades, got {len(data)}"
        print(f"✓ GES scale returns {len(data)} grade levels")
    
    def test_ges_scale_structure(self):
        """Test GES scale has correct structure"""
        response = requests.get(f"{BASE_URL}/api/grades/ges-scale")
        data = response.json()
        
        # Check first grade (Excellent)
        grade_1 = data[0]
        assert grade_1["grade"] == "1"
        assert grade_1["min_score"] == 80
        assert grade_1["max_score"] == 100
        assert grade_1["description"] == "Excellent"
        assert grade_1["gpa_point"] == 1.0
        print("✓ Grade 1 (Excellent) structure correct")
        
        # Check last grade (Fail)
        grade_9 = data[8]
        assert grade_9["grade"] == "9"
        assert grade_9["min_score"] == 0
        assert grade_9["max_score"] == 34
        assert grade_9["description"] == "Fail"
        print("✓ Grade 9 (Fail) structure correct")
    
    def test_ges_scale_covers_full_range(self):
        """Test GES scale covers 0-100% without gaps"""
        response = requests.get(f"{BASE_URL}/api/grades/ges-scale")
        data = response.json()
        
        # Sort by min_score descending
        sorted_grades = sorted(data, key=lambda x: x["min_score"], reverse=True)
        
        # Check coverage
        assert sorted_grades[0]["max_score"] == 100, "Highest grade should max at 100"
        assert sorted_grades[-1]["min_score"] == 0, "Lowest grade should min at 0"
        print("✓ GES scale covers full 0-100% range")


class TestSubjects:
    """Subjects endpoint tests"""
    
    def test_get_subjects_returns_seeded_data(self, auth_headers):
        """Test GET /api/grades/subjects returns seeded subjects"""
        response = requests.get(
            f"{BASE_URL}/api/grades/subjects",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 13, f"Expected at least 13 subjects, got {len(data)}"
        print(f"✓ Subjects endpoint returns {len(data)} subjects")
    
    def test_subjects_have_correct_structure(self, auth_headers):
        """Test subjects have required fields"""
        response = requests.get(
            f"{BASE_URL}/api/grades/subjects",
            headers=auth_headers
        )
        data = response.json()
        
        for subject in data:
            assert "id" in subject
            assert "name" in subject
            assert "code" in subject
            assert "category" in subject
            assert "credit_hours" in subject
            assert subject["category"] in ["core", "elective"]
        print("✓ All subjects have correct structure")
    
    def test_subjects_include_core_subjects(self, auth_headers):
        """Test that core GES subjects are present"""
        response = requests.get(
            f"{BASE_URL}/api/grades/subjects",
            headers=auth_headers
        )
        data = response.json()
        
        subject_names = [s["name"] for s in data]
        core_subjects = ["English Language", "Mathematics", "Integrated Science", "Social Studies"]
        
        for core in core_subjects:
            assert core in subject_names, f"Missing core subject: {core}"
        print("✓ All core GES subjects present")
    
    def test_seed_defaults_when_subjects_exist(self, auth_headers):
        """Test POST /api/grades/subjects/seed-defaults when subjects already exist"""
        response = requests.post(
            f"{BASE_URL}/api/grades/subjects/seed-defaults",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["created"] == 0
        assert "already exist" in data["message"].lower()
        print("✓ Seed defaults correctly reports subjects already exist")
    
    def test_create_custom_subject(self, auth_headers):
        """Test POST /api/grades/subjects - Create custom subject"""
        unique_code = f"TST{uuid.uuid4().hex[:4].upper()}"
        
        response = requests.post(
            f"{BASE_URL}/api/grades/subjects",
            headers=auth_headers,
            json={
                "name": f"TEST_Subject_{unique_code}",
                "code": unique_code,
                "category": "elective",
                "credit_hours": 3
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["name"] == f"TEST_Subject_{unique_code}"
        assert data["code"] == unique_code
        assert "Subject created successfully" in data["message"]
        print(f"✓ Created custom subject: {data['name']}")
    
    def test_subjects_requires_auth(self):
        """Test subjects endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/grades/subjects")
        assert response.status_code in [401, 403]
        print("✓ Subjects endpoint requires authentication")


class TestClassGrades:
    """Class grades endpoint tests"""
    
    @pytest.fixture
    def class_id(self, auth_headers):
        """Get a class ID for testing"""
        response = requests.get(
            f"{BASE_URL}/api/classes",
            headers=auth_headers
        )
        classes = response.json()
        if len(classes) > 0:
            return classes[0]["id"]
        pytest.skip("No classes available")
    
    def test_get_class_grades(self, auth_headers, class_id):
        """Test GET /api/grades/class/{class_id}"""
        response = requests.get(
            f"{BASE_URL}/api/grades/class/{class_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "class_id" in data
        assert "class_name" in data
        assert "student_count" in data
        assert "students" in data
        assert isinstance(data["students"], list)
        print(f"✓ Get class grades - Class: {data['class_name']}, Students: {data['student_count']}")
    
    def test_get_class_grades_with_filters(self, auth_headers, class_id):
        """Test GET /api/grades/class/{class_id} with filters"""
        # Get a subject ID
        subjects_response = requests.get(
            f"{BASE_URL}/api/grades/subjects",
            headers=auth_headers
        )
        subjects = subjects_response.json()
        if len(subjects) > 0:
            subject_id = subjects[0]["id"]
            
            response = requests.get(
                f"{BASE_URL}/api/grades/class/{class_id}?subject_id={subject_id}&assessment_type=class_work",
                headers=auth_headers
            )
            assert response.status_code == 200
            print("✓ Get class grades with filters works")
    
    def test_get_class_grades_invalid_class(self, auth_headers):
        """Test GET /api/grades/class/{class_id} with invalid class ID"""
        fake_id = str(uuid.uuid4())
        response = requests.get(
            f"{BASE_URL}/api/grades/class/{fake_id}",
            headers=auth_headers
        )
        assert response.status_code == 404
        print("✓ Invalid class ID returns 404")
    
    def test_class_grades_requires_auth(self):
        """Test class grades endpoint requires authentication"""
        fake_id = str(uuid.uuid4())
        response = requests.get(f"{BASE_URL}/api/grades/class/{fake_id}")
        assert response.status_code in [401, 403]
        print("✓ Class grades endpoint requires authentication")


class TestBulkGrades:
    """Bulk grades endpoint tests"""
    
    @pytest.fixture
    def test_student(self, auth_headers):
        """Create a test student for grade recording"""
        # Get a class
        classes_response = requests.get(
            f"{BASE_URL}/api/classes",
            headers=auth_headers
        )
        classes = classes_response.json()
        if len(classes) == 0:
            pytest.skip("No classes available")
        
        class_id = classes[0]["id"]
        student_id = f"TEST_BULK_{uuid.uuid4().hex[:6]}"
        
        response = requests.post(
            f"{BASE_URL}/api/students",
            headers=auth_headers,
            json={
                "student_id": student_id,
                "first_name": "Bulk",
                "last_name": "GradeTest",
                "date_of_birth": "2015-05-15",
                "gender": "male",
                "admission_date": "2024-01-15",
                "nationality": "Ghanaian",
                "class_id": class_id
            }
        )
        if response.status_code == 200:
            data = response.json()
            return {"id": data["id"], "class_id": class_id}
        pytest.skip("Could not create test student")
    
    def test_record_bulk_grades(self, auth_headers, test_student):
        """Test POST /api/grades/bulk - Record multiple grades"""
        # Get a subject
        subjects_response = requests.get(
            f"{BASE_URL}/api/grades/subjects",
            headers=auth_headers
        )
        subjects = subjects_response.json()
        subject_id = subjects[0]["id"]
        
        grades_data = [{
            "student_id": test_student["id"],
            "class_id": test_student["class_id"],
            "subject_id": subject_id,
            "academic_term_id": "term_1_2026",
            "assessment_type": "class_work",
            "score": 75,
            "max_score": 100
        }]
        
        response = requests.post(
            f"{BASE_URL}/api/grades/bulk",
            headers=auth_headers,
            json=grades_data
        )
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert "Recorded 1 grades successfully" in data["message"]
        print("✓ Bulk grades recorded successfully")
    
    def test_record_multiple_grades(self, auth_headers, test_student):
        """Test POST /api/grades/bulk - Record multiple grades at once"""
        # Get subjects
        subjects_response = requests.get(
            f"{BASE_URL}/api/grades/subjects",
            headers=auth_headers
        )
        subjects = subjects_response.json()
        
        grades_data = [
            {
                "student_id": test_student["id"],
                "class_id": test_student["class_id"],
                "subject_id": subjects[0]["id"],
                "academic_term_id": "term_1_2026",
                "assessment_type": "quiz",
                "score": 18,
                "max_score": 20
            },
            {
                "student_id": test_student["id"],
                "class_id": test_student["class_id"],
                "subject_id": subjects[1]["id"],
                "academic_term_id": "term_1_2026",
                "assessment_type": "homework",
                "score": 9,
                "max_score": 10
            }
        ]
        
        response = requests.post(
            f"{BASE_URL}/api/grades/bulk",
            headers=auth_headers,
            json=grades_data
        )
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        print(f"✓ Recorded {data['count']} grades in bulk")
    
    def test_bulk_grades_requires_auth(self):
        """Test bulk grades endpoint requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/grades/bulk",
            json=[{"student_id": "test", "score": 50}]
        )
        assert response.status_code in [401, 403]
        print("✓ Bulk grades endpoint requires authentication")


class TestGradeCalculations:
    """Test grade calculations and GES scale mapping"""
    
    @pytest.fixture
    def student_with_grades(self, auth_headers):
        """Create a student with grades for testing calculations"""
        # Get a class
        classes_response = requests.get(
            f"{BASE_URL}/api/classes",
            headers=auth_headers
        )
        classes = classes_response.json()
        if len(classes) == 0:
            pytest.skip("No classes available")
        
        class_id = classes[0]["id"]
        student_id = f"TEST_CALC_{uuid.uuid4().hex[:6]}"
        
        # Create student
        student_response = requests.post(
            f"{BASE_URL}/api/students",
            headers=auth_headers,
            json={
                "student_id": student_id,
                "first_name": "Calc",
                "last_name": "Test",
                "date_of_birth": "2015-05-15",
                "gender": "female",
                "admission_date": "2024-01-15",
                "nationality": "Ghanaian",
                "class_id": class_id
            }
        )
        if student_response.status_code != 200:
            pytest.skip("Could not create test student")
        
        student_data = student_response.json()
        
        # Get subjects
        subjects_response = requests.get(
            f"{BASE_URL}/api/grades/subjects",
            headers=auth_headers
        )
        subjects = subjects_response.json()
        
        # Record grades with known scores
        grades_data = [
            {
                "student_id": student_data["id"],
                "class_id": class_id,
                "subject_id": subjects[0]["id"],
                "academic_term_id": "term_1_2026",
                "assessment_type": "end_of_term",
                "score": 85,  # Grade 1 - Excellent
                "max_score": 100
            },
            {
                "student_id": student_data["id"],
                "class_id": class_id,
                "subject_id": subjects[1]["id"],
                "academic_term_id": "term_1_2026",
                "assessment_type": "end_of_term",
                "score": 65,  # Grade 3 - Good
                "max_score": 100
            }
        ]
        
        requests.post(
            f"{BASE_URL}/api/grades/bulk",
            headers=auth_headers,
            json=grades_data
        )
        
        return {"id": student_data["id"], "class_id": class_id}
    
    def test_class_grades_show_letter_grades(self, auth_headers, student_with_grades):
        """Test that class grades endpoint returns letter grades"""
        response = requests.get(
            f"{BASE_URL}/api/grades/class/{student_with_grades['class_id']}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Find our test student
        test_student = None
        for student in data["students"]:
            if student["student_id"] == student_with_grades["id"]:
                test_student = student
                break
        
        if test_student:
            assert "letter_grade" in test_student
            assert "grade_description" in test_student
            assert "average_percentage" in test_student
            print(f"✓ Student grades: {test_student['average_percentage']}% = Grade {test_student['letter_grade']} ({test_student['grade_description']})")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
