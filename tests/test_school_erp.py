"""
School ERP System - Backend API Tests
Tests for: Auth, Dashboard, Students, Staff, Classes, Attendance, Announcements
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
SCHOOL_ADMIN_EMAIL = "admin@school.edu.gh"
SCHOOL_ADMIN_PASSWORD = "admin123"
SUPER_ADMIN_EMAIL = "superadmin@schoolerp.com"
SUPER_ADMIN_PASSWORD = "admin123"
TEACHER_EMAIL = "teacher@school.edu.gh"
TEACHER_PASSWORD = "teacher123"


class TestHealthCheck:
    """Health check endpoint tests"""
    
    def test_health_endpoint(self):
        """Test /api/health returns healthy status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("✓ Health check passed")
    
    def test_api_root(self):
        """Test /api root endpoint"""
        response = requests.get(f"{BASE_URL}/api")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["status"] == "running"
        print("✓ API root endpoint passed")


class TestAuthentication:
    """Authentication endpoint tests"""
    
    def test_login_school_admin_success(self):
        """Test login with valid school admin credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SCHOOL_ADMIN_EMAIL,
            "password": SCHOOL_ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == SCHOOL_ADMIN_EMAIL
        assert data["user"]["role"] == "school_admin"
        print(f"✓ School admin login successful - User: {data['user']['first_name']} {data['user']['last_name']}")
    
    def test_login_super_admin_success(self):
        """Test login with valid super admin credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["role"] == "super_admin"
        print("✓ Super admin login successful")
    
    def test_login_teacher_success(self):
        """Test login with valid teacher credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEACHER_EMAIL,
            "password": TEACHER_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["role"] == "teacher"
        print("✓ Teacher login successful")
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials returns 401"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "wrong@example.com",
            "password": "wrongpassword"
        })
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        print("✓ Invalid credentials correctly rejected")
    
    def test_login_wrong_password(self):
        """Test login with wrong password"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SCHOOL_ADMIN_EMAIL,
            "password": "wrongpassword"
        })
        assert response.status_code == 401
        print("✓ Wrong password correctly rejected")
    
    def test_get_me_authenticated(self):
        """Test /api/auth/me with valid token"""
        # First login
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SCHOOL_ADMIN_EMAIL,
            "password": SCHOOL_ADMIN_PASSWORD
        })
        token = login_response.json()["access_token"]
        
        # Get current user
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == SCHOOL_ADMIN_EMAIL
        assert "id" in data
        assert "first_name" in data
        assert "last_name" in data
        print("✓ Get current user successful")
    
    def test_get_me_unauthenticated(self):
        """Test /api/auth/me without token returns 401 or 403"""
        response = requests.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code in [401, 403]
        print("✓ Unauthenticated request correctly rejected")


class TestRegistration:
    """Registration endpoint tests"""
    
    def test_register_school_admin(self):
        """Test registration for school_admin role"""
        import uuid
        unique_email = f"test_admin_{uuid.uuid4().hex[:8]}@school.edu.gh"
        
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": "testpass123",
            "first_name": "Test",
            "last_name": "Admin",
            "phone": "+233 20 333 3333",
            "role": "school_admin"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["email"] == unique_email
        assert data["user"]["role"] == "school_admin"
        print(f"✓ Registration successful for {unique_email}")
    
    def test_register_duplicate_email(self):
        """Test registration with existing email fails"""
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": SCHOOL_ADMIN_EMAIL,
            "password": "testpass123",
            "first_name": "Duplicate",
            "last_name": "User",
            "role": "school_admin"
        })
        assert response.status_code == 400
        data = response.json()
        assert "already registered" in data["detail"].lower()
        print("✓ Duplicate email correctly rejected")
    
    def test_register_super_admin_forbidden(self):
        """Test that super_admin registration is forbidden"""
        import uuid
        unique_email = f"test_super_{uuid.uuid4().hex[:8]}@school.edu.gh"
        
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": "testpass123",
            "first_name": "Test",
            "last_name": "Super",
            "role": "super_admin"
        })
        assert response.status_code == 403
        print("✓ Super admin registration correctly forbidden")


@pytest.fixture
def auth_token():
    """Get authentication token for school admin"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": SCHOOL_ADMIN_EMAIL,
        "password": SCHOOL_ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json()["access_token"]
    pytest.skip("Authentication failed")


@pytest.fixture
def auth_headers(auth_token):
    """Get headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestDashboard:
    """Dashboard endpoint tests"""
    
    def test_dashboard_overview(self, auth_headers):
        """Test dashboard overview endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/overview",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "role" in data
        assert "stats" in data
        stats = data["stats"]
        assert "total_students" in stats
        assert "total_teachers" in stats
        assert "total_classes" in stats
        print(f"✓ Dashboard overview - Students: {stats['total_students']}, Teachers: {stats['total_teachers']}, Classes: {stats['total_classes']}")
    
    def test_dashboard_overview_unauthenticated(self):
        """Test dashboard overview without auth returns 401 or 403"""
        response = requests.get(f"{BASE_URL}/api/dashboard/overview")
        assert response.status_code in [401, 403]
        print("✓ Dashboard correctly requires authentication")


class TestStudents:
    """Students endpoint tests"""
    
    def test_list_students(self, auth_headers):
        """Test listing students"""
        response = requests.get(
            f"{BASE_URL}/api/students",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert isinstance(data["items"], list)
        print(f"✓ List students - Total: {data['total']}, Page: {data['page']}")
    
    def test_list_students_with_search(self, auth_headers):
        """Test listing students with search"""
        response = requests.get(
            f"{BASE_URL}/api/students?search=test",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        print(f"✓ Search students - Found: {len(data['items'])}")
    
    def test_create_student(self, auth_headers):
        """Test creating a new student"""
        import uuid
        student_id = f"TEST_STU_{uuid.uuid4().hex[:6]}"
        
        response = requests.post(
            f"{BASE_URL}/api/students",
            headers=auth_headers,
            json={
                "student_id": student_id,
                "first_name": "Test",
                "last_name": "Student",
                "date_of_birth": "2015-05-15",
                "gender": "male",
                "admission_date": "2024-01-15",
                "nationality": "Ghanaian"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["student_id"] == student_id
        assert data["first_name"] == "Test"
        print(f"✓ Created student: {student_id}")
        return data["id"]
    
    def test_create_student_duplicate_id(self, auth_headers):
        """Test creating student with duplicate ID fails"""
        import uuid
        student_id = f"TEST_DUP_{uuid.uuid4().hex[:6]}"
        
        # Create first student
        requests.post(
            f"{BASE_URL}/api/students",
            headers=auth_headers,
            json={
                "student_id": student_id,
                "first_name": "First",
                "last_name": "Student",
                "date_of_birth": "2015-05-15",
                "gender": "male",
                "admission_date": "2024-01-15"
            }
        )
        
        # Try to create duplicate
        response = requests.post(
            f"{BASE_URL}/api/students",
            headers=auth_headers,
            json={
                "student_id": student_id,
                "first_name": "Duplicate",
                "last_name": "Student",
                "date_of_birth": "2015-06-15",
                "gender": "female",
                "admission_date": "2024-01-15"
            }
        )
        assert response.status_code == 400
        print("✓ Duplicate student ID correctly rejected")


class TestStaff:
    """Staff endpoint tests"""
    
    def test_list_staff(self, auth_headers):
        """Test listing staff"""
        response = requests.get(
            f"{BASE_URL}/api/staff",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        print(f"✓ List staff - Total: {data['total']}")
    
    def test_list_teachers(self, auth_headers):
        """Test listing teachers only"""
        response = requests.get(
            f"{BASE_URL}/api/staff/teachers",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ List teachers - Count: {len(data)}")
    
    def test_create_staff(self, auth_headers):
        """Test creating a new staff member"""
        import uuid
        staff_id = f"TEST_STF_{uuid.uuid4().hex[:6]}"
        
        response = requests.post(
            f"{BASE_URL}/api/staff",
            headers=auth_headers,
            json={
                "staff_id": staff_id,
                "first_name": "Test",
                "last_name": "Teacher",
                "email": f"test_{uuid.uuid4().hex[:6]}@school.edu.gh",
                "phone": "+233 20 444 4444",
                "date_of_birth": "1985-03-20",
                "gender": "female",
                "staff_type": "teaching",
                "position": "Mathematics Teacher",
                "department": "Science",
                "date_joined": "2024-01-01"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["staff_id"] == staff_id
        print(f"✓ Created staff: {staff_id}")


class TestClasses:
    """Classes endpoint tests"""
    
    def test_list_classes(self, auth_headers):
        """Test listing classes"""
        response = requests.get(
            f"{BASE_URL}/api/classes",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ List classes - Count: {len(data)}")
        
        # Verify class structure
        if len(data) > 0:
            cls = data[0]
            assert "id" in cls
            assert "name" in cls
            assert "level" in cls
            assert "capacity" in cls
            print(f"  First class: {cls['name']} (Level: {cls['level']})")
    
    def test_create_class(self, auth_headers):
        """Test creating a new class"""
        import uuid
        class_name = f"TEST_Class_{uuid.uuid4().hex[:4]}"
        
        response = requests.post(
            f"{BASE_URL}/api/classes",
            headers=auth_headers,
            json={
                "name": class_name,
                "level": "primary_3",
                "section": "A",
                "capacity": 35,
                "room_number": "TEST101"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == class_name
        assert data["level"] == "primary_3"
        print(f"✓ Created class: {class_name}")
        return data["id"]
    
    def test_get_class_details(self, auth_headers):
        """Test getting class details"""
        # First get list of classes
        list_response = requests.get(
            f"{BASE_URL}/api/classes",
            headers=auth_headers
        )
        classes = list_response.json()
        
        if len(classes) > 0:
            class_id = classes[0]["id"]
            response = requests.get(
                f"{BASE_URL}/api/classes/{class_id}",
                headers=auth_headers
            )
            assert response.status_code == 200
            data = response.json()
            assert "students" in data
            assert "subjects" in data
            print(f"✓ Get class details - {data['name']}, Students: {data['student_count']}")
        else:
            pytest.skip("No classes available")


class TestAttendance:
    """Attendance endpoint tests"""
    
    def test_get_class_attendance(self, auth_headers):
        """Test getting class attendance"""
        # First get a class
        classes_response = requests.get(
            f"{BASE_URL}/api/classes",
            headers=auth_headers
        )
        classes = classes_response.json()
        
        if len(classes) > 0:
            class_id = classes[0]["id"]
            from datetime import date
            today = date.today().isoformat()
            
            response = requests.get(
                f"{BASE_URL}/api/attendance/class/{class_id}?attendance_date={today}",
                headers=auth_headers
            )
            assert response.status_code == 200
            data = response.json()
            assert "class_name" in data
            assert "summary" in data
            assert "records" in data
            print(f"✓ Get class attendance - Class: {data['class_name']}, Records: {len(data['records'])}")
        else:
            pytest.skip("No classes available")


class TestAnnouncements:
    """Announcements endpoint tests"""
    
    def test_list_announcements(self, auth_headers):
        """Test listing announcements"""
        response = requests.get(
            f"{BASE_URL}/api/communication/announcements",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        print(f"✓ List announcements - Total: {data['total']}")
    
    def test_create_announcement(self, auth_headers):
        """Test creating an announcement"""
        import uuid
        from datetime import datetime
        
        response = requests.post(
            f"{BASE_URL}/api/communication/announcements",
            headers=auth_headers,
            json={
                "title": f"TEST_Announcement_{uuid.uuid4().hex[:6]}",
                "content": "This is a test announcement content.",
                "announcement_type": "general",
                "audience": "all",
                "is_published": True,
                "publish_date": datetime.utcnow().isoformat()
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["announcement_type"] == "general"
        print(f"✓ Created announcement: {data['title']}")


class TestProtectedRoutes:
    """Test that protected routes require authentication"""
    
    def test_students_requires_auth(self):
        """Test students endpoint requires auth"""
        response = requests.get(f"{BASE_URL}/api/students")
        assert response.status_code in [401, 403]
        print("✓ Students endpoint requires auth")
    
    def test_staff_requires_auth(self):
        """Test staff endpoint requires auth"""
        response = requests.get(f"{BASE_URL}/api/staff")
        assert response.status_code in [401, 403]
        print("✓ Staff endpoint requires auth")
    
    def test_classes_requires_auth(self):
        """Test classes endpoint requires auth"""
        response = requests.get(f"{BASE_URL}/api/classes")
        assert response.status_code in [401, 403]
        print("✓ Classes endpoint requires auth")
    
    def test_announcements_requires_auth(self):
        """Test announcements endpoint requires auth"""
        response = requests.get(f"{BASE_URL}/api/communication/announcements")
        assert response.status_code in [401, 403]
        print("✓ Announcements endpoint requires auth")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
