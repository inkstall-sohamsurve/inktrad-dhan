"""
Simple test script to verify API functionality.
Run this after starting the server to test basic endpoints.
"""
import requests
import json
from typing import Optional

BASE_URL = "http://localhost:8000"

class InktradAPITester:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.token: Optional[str] = None
        self.test_username = "testuser_" + str(hash("test"))[:8]
        self.test_email = f"{self.test_username}@example.com"
        self.test_password = "TestPassword123!"
    
    def print_response(self, response: requests.Response, title: str):
        """Pretty print API response."""
        print(f"\n{'='*60}")
        print(f"TEST: {title}")
        print(f"{'='*60}")
        print(f"Status Code: {response.status_code}")
        try:
            print(f"Response: {json.dumps(response.json(), indent=2)}")
        except:
            print(f"Response: {response.text}")
        print(f"{'='*60}\n")
    
    def test_health(self):
        """Test health endpoint."""
        response = requests.get(f"{self.base_url}/health")
        self.print_response(response, "Health Check")
        return response.status_code == 200
    
    def test_register(self):
        """Test user registration."""
        data = {
            "username": self.test_username,
            "email": self.test_email,
            "password": self.test_password
        }
        response = requests.post(f"{self.base_url}/auth/register", json=data)
        self.print_response(response, "User Registration")
        return response.status_code in [200, 201, 400]  # 400 if user exists
    
    def test_login(self):
        """Test user login."""
        data = {
            "username": self.test_username,
            "password": self.test_password
        }
        response = requests.post(f"{self.base_url}/auth/login", json=data)
        self.print_response(response, "User Login")
        
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            print(f"✅ Token obtained: {self.token[:20]}...")
            return True
        return False
    
    def test_get_profile(self):
        """Test get current user profile."""
        if not self.token:
            print("❌ No token available. Login first.")
            return False
        
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(f"{self.base_url}/auth/me", headers=headers)
        self.print_response(response, "Get User Profile")
        return response.status_code == 200
    
    def test_create_watchlist(self):
        """Test watchlist creation."""
        if not self.token:
            print("❌ No token available. Login first.")
            return False
        
        headers = {"Authorization": f"Bearer {self.token}"}
        data = {
            "name": "Test Watchlist",
            "instruments": [
                {
                    "security_id": "1333",
                    "symbol": "RELIANCE",
                    "exchange_segment": "NSE_EQ"
                }
            ]
        }
        response = requests.post(
            f"{self.base_url}/api/v2/watchlist",
            json=data,
            headers=headers
        )
        self.print_response(response, "Create Watchlist")
        return response.status_code in [200, 201, 400]  # 400 if exists
    
    def test_get_watchlists(self):
        """Test get all watchlists."""
        if not self.token:
            print("❌ No token available. Login first.")
            return False
        
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(
            f"{self.base_url}/api/v2/watchlist",
            headers=headers
        )
        self.print_response(response, "Get All Watchlists")
        return response.status_code == 200
    
    def run_all_tests(self):
        """Run all tests."""
        print("\n" + "="*60)
        print("INKTRAD API TEST SUITE")
        print("="*60)
        
        tests = [
            ("Health Check", self.test_health),
            ("User Registration", self.test_register),
            ("User Login", self.test_login),
            ("Get Profile", self.test_get_profile),
            ("Create Watchlist", self.test_create_watchlist),
            ("Get Watchlists", self.test_get_watchlists),
        ]
        
        results = []
        for test_name, test_func in tests:
            try:
                result = test_func()
                results.append((test_name, result))
            except Exception as e:
                print(f"❌ {test_name} failed with error: {e}")
                results.append((test_name, False))
        
        # Print summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        for test_name, result in results:
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"{test_name}: {status}")
        
        passed = sum(1 for _, result in results if result)
        total = len(results)
        print(f"\nTotal: {passed}/{total} tests passed")
        print("="*60 + "\n")


def main():
    """Main test function."""
    print("Starting Inktrad API Tests...")
    print(f"Base URL: {BASE_URL}")
    print("\nMake sure the server is running before running these tests!")
    print("Start server with: python run.py\n")
    
    input("Press Enter to continue...")
    
    tester = InktradAPITester()
    tester.run_all_tests()


if __name__ == "__main__":
    main()
