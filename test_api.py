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
BASE_URL = "http://194.59.165.202:81"  # Change this to your VPS IP and port
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

def test_health_check():
    """Test health check endpoint"""
    print_header("1. Testing Health Check")
    try:
        response = requests.get(f"{API_BASE}/health", timeout=5)
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
            timeout=10
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
            timeout=10
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
            timeout=10
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
        response = requests.get(BASE_URL, timeout=5)
        print(f"Frontend Status Code: {response.status_code}")
        print_test("Frontend Accessible", response.status_code in [200, 304], f"Status: {response.status_code}")
        
        # Test API proxy
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        print(f"API Proxy Status Code: {response.status_code}")
        print_test("API Proxy", response.status_code == 200, f"Status: {response.status_code}")
        
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        print_test("Nginx Proxy", False, f"Connection error: {str(e)}")
        return False

def run_all_tests():
    """Run all API tests"""
    print(f"\n{BLUE}╔{'═'*58}╗{RESET}")
    print(f"{BLUE}║{' '*15}LocalAIChatBox API Test Suite{' '*15}║{RESET}")
    print(f"{BLUE}║{' '*20}VPS: 194.59.165.202:81{' '*20}║{RESET}")
    print(f"{BLUE}║{' '*16}Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{' '*17}║{RESET}")
    print(f"{BLUE}╚{'═'*58}╝{RESET}")
    
    results = {}
    
    # Test 0: Nginx Proxy
    results['nginx'] = test_nginx_proxy()
    
    # Test 1: Health Check
    results['health'] = test_health_check()
    
    if not results['health']:
        print(f"\n{RED}⚠️  Health check failed! Backend may not be running.{RESET}")
        print(f"{YELLOW}Run on VPS: docker-compose logs backend --tail=50{RESET}")
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
        return True
    else:
        print(f"\n{RED}✗ Some tests failed. Check the details above.{RESET}")
        print(f"\n{YELLOW}Troubleshooting steps:{RESET}")
        print(f"1. SSH to VPS: ssh root@194.59.165.202")
        print(f"2. Check backend logs: docker-compose logs backend --tail=100")
        print(f"3. Check database: docker-compose ps postgres")
        print(f"4. Restart backend: docker-compose restart backend")
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
