#!/usr/bin/env python3
"""
API Health Test Script for LocalAIChatBox
Test all API endpoints to verify functionality
"""

import requests
import json
import sys
from datetime import datetime

# Configuration
BASE_URL = "http://194.59.xxx.xxx:81"  # Change this to your VPS IP and port
API_BASE = f"{BASE_URL}/api"

# Colors for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_header(text):
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}{text:^60}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")

def print_test(name, status, details=""):
    status_text = f"{GREEN}✓ PASS{RESET}" if status else f"{RED}✗ FAIL{RESET}"
    print(f"{status_text} - {name}")
    if details:
        print(f"  {YELLOW}→{RESET} {details}")

def check_backend_reachable():
    """Quick check if backend is reachable at all"""
    print(f"{YELLOW}Kiểm tra kết nối đến VPS...{RESET}")
    try:
        # Try a simple GET to root
        response = requests.get(BASE_URL, timeout=10)
        print(f"{GREEN}✓ Frontend đang chạy (HTTP {response.status_code}){RESET}")
        return True
    except requests.exceptions.Timeout:
        print(f"{RED}✗ Timeout: Không kết nối được đến {BASE_URL}{RESET}")
        print(f"{YELLOW}Kiểm tra:{RESET}")
        print(f"  1. VPS có đang chạy không?")
        print(f"  2. Port 81 có mở không? (firewall)")
        print(f"  3. Docker containers có đang chạy? docker-compose ps")
        return False
    except requests.exceptions.ConnectionError:
        print(f"{RED}✗ Connection Error: Không thể kết nối đến VPS{RESET}") 
        print(f"{YELLOW}Kiểm tra:{RESET}")
        print(f"  1. IP và port đúng không? {BASE_URL}")
        print(f"  2. VPS có đang chạy?")
        print(f"  3. Firewall có block port 81?")
        return False
    except Exception as e:
        print(f"{RED}✗ Error: {str(e)}{RESET}")
        return False

def test_health_check():
    """Test health check endpoint"""
    print_header("1. Testing Health Check")
    try:
        print(f"Connecting to: {API_BASE}/health")
        response = requests.get(f"{API_BASE}/health", timeout=30)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            
            # Check database status
            db_ok = data.get("services", {}).get("database") == "ok"
            print_test("Database Connection", db_ok, data.get("services", {}).get("database"))
            
            # Check Ollama status (optional)
            ollama_status = data.get("services", {}).get("ollama", "unknown")
            print_test("Ollama Service", ollama_status == "ok", ollama_status)
            
            return db_ok
        else:
            print_test("Health Check", False, f"Status code: {response.status_code}")
            return False
    except requests.exceptions.Timeout as e:
        print_test("Health Check", False, "Timeout: Backend không phản hồi (>30s). Kiểm tra: docker-compose ps backend")
        return False
    except requests.exceptions.RequestException as e:
        print_test("Health Check", False, f"Connection error: {str(e)}")
        return False

def test_register(username, email, password):
    """Test user registration"""
    print_header("2. Testing User Registration")
    try:
        payload = {
            "username": username,
            "email": email,
            "full_name": f"Test User {username}",
            "password": password
        }
        print(f"Payload: {json.dumps(payload, indent=2)}")
        
        response = requests.post(
            f"{API_BASE}/auth/register",
            json=payload,
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        
        if response.status_code == 200:
            data = response.json()
            print_test("User Registration", True, f"User created: {data.get('user', {}).get('username')}")
            return data.get("access_token"), data
        elif response.status_code == 400:
            print_test("User Registration", False, "User already exists (expected if testing multiple times)")
            return None, None
        else:
            print_test("User Registration", False, f"Unexpected status: {response.status_code}")
            return None, None
    except requests.exceptions.Timeout:
        print_test("User Registration", False, "Timeout: Backend quá chậm")
        return None, None
    except requests.exceptions.RequestException as e:
        print_test("User Registration", False, f"Connection error: {str(e)}")
        return None, None

def test_login(username, password):
    """Test user login"""
    print_header("3. Testing User Login")
    try:
        payload = {
            "username": username,
            "password": password
        }
        print(f"Payload: {json.dumps(payload, indent=2)}")
        
        response = requests.post(
            f"{API_BASE}/auth/login",
            json=payload,
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        
        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token")
            user = data.get("user", {})
            print_test("User Login", True, f"Logged in as: {user.get('username')}")
            print(f"  Token: {token[:50]}...")
            return token, data
        else:
            print_test("User Login", False, f"Status: {response.status_code}, Response: {response.text}")
            return None, None
    except requests.exceptions.Timeout:
        print_test("User Login", False, "Timeout: Backend quá chậm")
        return None, None
    except requests.exceptions.RequestException as e:
        print_test("User Login", False, f"Connection error: {str(e)}")
        return None, None

def test_get_me(token):
    """Test get current user endpoint"""
    print_header("4. Testing Get Current User (/auth/me)")
    try:
        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        response = requests.get(
            f"{API_BASE}/auth/me",
            headers=headers,
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            print_test("Get Current User", True, f"User: {data.get('username')}")
            return True
        else:
            print_test("Get Current User", False, f"Status: {response.status_code}")
            return False
    except requests.exceptions.Timeout:
        print_test("Get Current User", False, "Timeout")
        return False
    except requests.exceptions.RequestException as e:
        print_test("Get Current User", False, f"Connection error: {str(e)}")
        return False

def test_default_admin_login():
    """Test default admin login"""
    print_header("5. Testing Default Admin Login")
    return test_login("admin", "admin123")

def test_nginx_proxy():
    """Test if nginx is properly proxying requests"""
    print_header("0. Testing Nginx Proxy")
    try:
        # Test root endpoint
        print(f"Testing frontend: {BASE_URL}")
        response = requests.get(BASE_URL, timeout=15)
        print(f"Frontend Status Code: {response.status_code}")
        print_test("Frontend Accessible", response.status_code in [200, 304], f"Status: {response.status_code}")
        
        # Test API proxy
        print(f"\nTesting API proxy: {BASE_URL}/api/health")
        response = requests.get(f"{BASE_URL}/api/health", timeout=30)
        print(f"API Proxy Status Code: {response.status_code}")
        print_test("API Proxy", response.status_code == 200, f"Status: {response.status_code}")
        
        return response.status_code == 200
    except requests.exceptions.Timeout as e:
        print_test("Nginx Proxy", False, f"Timeout error: Backend is too slow or not responding. Try: docker-compose restart backend")
        return False
    except requests.exceptions.RequestException as e:
        print_test("Nginx Proxy", False, f"Connection error: {str(e)}")
        return False

def run_all_tests():
    """Run all API tests"""
    print(f"\n{BLUE}╔{'═'*58}╗{RESET}")
    print(f"{BLUE}║{' '*15}LocalAIChatBox API Test Suite{' '*15}║{RESET}")
    print(f"{BLUE}║{' '*20}VPS: 194.59.xxx.xxx:81{' '*20}║{RESET}")
    print(f"{BLUE}║{' '*16}Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{' '*17}║{RESET}")
    print(f"{BLUE}╚{'═'*58}╝{RESET}\n")
    
    # Pre-check: Can we reach the server at all?
    if not check_backend_reachable():
        print(f"\n{RED}❌ Không thể kết nối đến VPS. Dừng test.{RESET}")
        return False
    
    print(f"\n{GREEN}✓ VPS có thể truy cập được. Bắt đầu test API...{RESET}\n")
    
    results = {}
    
    # Test 0: Nginx Proxy
    results['nginx'] = test_nginx_proxy()
    
    # Test 1: Health Check
    results['health'] = test_health_check()
    
    if not results['health']:
        print(f"\n{RED}⚠️  Health check failed! Backend có thể không chạy hoặc quá chậm.{RESET}")
        print(f"\n{YELLOW}Các bước kiểm tra trên VPS:{RESET}")
        print(f"  1. SSH: ssh root@194.59.xxx.xxx")
        print(f"  2. Vào thư mục: cd ~/LocalAIChatBox")
        print(f"  3. Xem containers: docker-compose ps")
        print(f"  4. Xem logs backend: docker-compose logs backend --tail=100")
        print(f"  5. Test local: curl http://localhost:8001/api/health")
        print(f"  6. Restart nếu cần: docker-compose restart backend")
        return False
    
    # Test 2 & 3: Register and Login
    test_user = f"testuser_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    test_email = f"{test_user}@test.com"
    test_password = "Test123456"
    
    token, user_data = test_register(test_user, test_email, test_password)
    
    if not token:
        # If registration failed (user exists), try login
        token, user_data = test_login(test_user, test_password)
    
    results['auth'] = token is not None
    
    # Test 4: Get Current User
    if token:
        results['get_me'] = test_get_me(token)
    else:
        results['get_me'] = False
    
    # Test 5: Default Admin Login
    admin_token, admin_data = test_default_admin_login()
    results['admin_login'] = admin_token is not None
    
    # Print Summary
    print_header("TEST SUMMARY")
    
    total_tests = len(results)
    passed_tests = sum(1 for v in results.values() if v)
    
    for test_name, passed in results.items():
        status = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
        print(f"  {test_name.upper():20} [{status}]")
    
    print(f"\n{BLUE}{'─'*60}{RESET}")
    print(f"Total: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print(f"{GREEN}✓ All tests passed! API is working correctly.{RESET}")
        print(f"\n{GREEN}🎉 Bạn có thể truy cập frontend và đăng nhập:{RESET}")
        print(f"   👉 http://194.59.xxx.xxx:81")
        print(f"   Username: admin")
        print(f"   Password: admin123")
        return True
    else:
        print(f"\n{RED}✗ Some tests failed. Check the details above.{RESET}")
        print(f"\n{YELLOW}📋 Troubleshooting Steps:{RESET}")
        print(f"\n{BLUE}Bước 1: SSH vào VPS{RESET}")
        print(f"  ssh root@194.59.xxx.xxx")
        print(f"\n{BLUE}Bước 2: Kiểm tra containers{RESET}")
        print(f"  cd ~/LocalAIChatBox")
        print(f"  docker-compose ps")
        print(f"\n{BLUE}Bước 3: Xem logs chi tiết{RESET}")
        print(f"  docker-compose logs backend --tail=100")
        print(f"  docker-compose logs nginx --tail=50")
        print(f"  docker-compose logs postgres --tail=30")
        print(f"\n{BLUE}Bước 4: Test trực tiếp trên VPS{RESET}")
        print(f"  curl http://localhost:8001/api/health")
        print(f"  curl http://localhost:81/api/health")
        print(f"\n{BLUE}Bước 5: Restart nếu cần{RESET}")
        print(f"  docker-compose restart backend")
        print(f"  # Hoặc rebuild: docker-compose build backend && docker-compose up -d backend")
        print(f"\n{YELLOW}💡 Lỗi thường gặp:{RESET}")
        print(f"  • Backend timeout → Check logs, có thể thiếu dependencies")
        print(f"  • Database error → Restart postgres: docker-compose restart postgres")
        print(f"  • 500 error → Check backend logs có Python errors")
        print(f"  • Nginx 502 → Backend chưa sẵn sàng, đợi thêm 30s")
        return False

if __name__ == "__main__":
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Test interrupted by user{RESET}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{RED}Unexpected error: {str(e)}{RESET}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
