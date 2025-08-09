import requests
import sys
import json
from datetime import datetime
import uuid

class QAPlatformTester:
    def __init__(self, base_url="https://8fd24260-95b7-4b56-9eff-53e32c8ede59.preview.emergentagent.com"):
        self.base_url = base_url
        self.token = None
        self.user_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_user_data = {
            "username": f"testuser_{datetime.now().strftime('%H%M%S')}",
            "email": f"test_{datetime.now().strftime('%H%M%S')}@example.com",
            "password": "TestPass123!",
            "full_name": "Test User",
            "bio": "Test user for API testing"
        }

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}{endpoint}"
        test_headers = {'Content-Type': 'application/json'}
        
        if self.token:
            test_headers['Authorization'] = f'Bearer {self.token}'
        
        if headers:
            test_headers.update(headers)

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=test_headers)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=test_headers)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=test_headers)
            elif method == 'DELETE':
                response = requests.delete(url, headers=test_headers)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    print(f"   Response: {json.dumps(response_data, indent=2)[:200]}...")
                    return True, response_data
                except:
                    return True, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data}")
                except:
                    print(f"   Error: {response.text}")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_health_check(self):
        """Test health endpoint"""
        return self.run_test("Health Check", "GET", "/api/health", 200)

    def test_register(self):
        """Test user registration"""
        success, response = self.run_test(
            "User Registration",
            "POST",
            "/api/register",
            200,
            data=self.test_user_data
        )
        if success and 'access_token' in response:
            self.token = response['access_token']
            return True
        return False

    def test_login(self):
        """Test user login"""
        login_data = {
            "username": self.test_user_data["username"],
            "password": self.test_user_data["password"]
        }
        success, response = self.run_test(
            "User Login",
            "POST",
            "/api/login",
            200,
            data=login_data
        )
        if success and 'access_token' in response:
            self.token = response['access_token']
            return True
        return False

    def test_get_user_info(self):
        """Test getting current user info"""
        success, response = self.run_test(
            "Get User Info",
            "GET",
            "/api/me",
            200
        )
        if success and 'id' in response:
            self.user_id = response['id']
            return True
        return False

    def test_create_question(self):
        """Test creating a question"""
        question_data = {
            "title": "Test Question - How to test APIs?",
            "content": "I'm trying to understand how to properly test REST APIs. What are the best practices?",
            "tags": ["testing", "api", "best-practices"]
        }
        success, response = self.run_test(
            "Create Question",
            "POST",
            "/api/questions",
            200,
            data=question_data
        )
        return response.get('id') if success else None

    def test_get_questions(self):
        """Test getting questions list"""
        success, response = self.run_test(
            "Get Questions List",
            "GET",
            "/api/questions",
            200
        )
        return response if success else []

    def test_get_question_detail(self, question_id):
        """Test getting question details"""
        success, response = self.run_test(
            "Get Question Detail",
            "GET",
            f"/api/questions/{question_id}",
            200
        )
        return success

    def test_create_answer(self, question_id):
        """Test creating an answer"""
        answer_data = {
            "content": "Great question! Here are some best practices for API testing:\n1. Test all HTTP methods\n2. Verify status codes\n3. Check response data\n4. Test error scenarios\n5. Validate authentication"
        }
        success, response = self.run_test(
            "Create Answer",
            "POST",
            f"/api/questions/{question_id}/answers",
            200,
            data=answer_data
        )
        return response.get('id') if success else None

    def test_get_answers(self, question_id):
        """Test getting answers for a question"""
        success, response = self.run_test(
            "Get Answers",
            "GET",
            f"/api/questions/{question_id}/answers",
            200
        )
        return response if success else []

    def test_vote_question(self, question_id, value=1):
        """Test voting on a question"""
        vote_data = {
            "user_id": self.user_id,
            "target_id": question_id,
            "target_type": "question",
            "value": value
        }
        success, response = self.run_test(
            f"Vote Question ({'upvote' if value > 0 else 'downvote'})",
            "POST",
            "/api/vote",
            200,
            data=vote_data
        )
        return success

    def test_vote_answer(self, answer_id, value=1):
        """Test voting on an answer"""
        vote_data = {
            "user_id": self.user_id,
            "target_id": answer_id,
            "target_type": "answer",
            "value": value
        }
        success, response = self.run_test(
            f"Vote Answer ({'upvote' if value > 0 else 'downvote'})",
            "POST",
            "/api/vote",
            200,
            data=vote_data
        )
        return success

    def test_search_questions(self, query="testing"):
        """Test search functionality"""
        success, response = self.run_test(
            "Search Questions",
            "GET",
            f"/api/search?q={query}",
            200
        )
        return response if success else []

    def test_ai_chat(self):
        """Test AI chat functionality"""
        chat_data = {
            "message": "Hello AI! Can you help me understand how to write better questions on this platform?"
        }
        success, response = self.run_test(
            "AI Chat",
            "POST",
            "/api/chat",
            200,
            data=chat_data
        )
        return success and 'response' in response

def main():
    print("🚀 Starting Q&A Platform API Tests")
    print("=" * 50)
    
    tester = QAPlatformTester()
    
    # Test sequence
    print("\n📋 Running Backend API Tests...")
    
    # 1. Health check
    if not tester.test_health_check()[0]:
        print("❌ Health check failed, stopping tests")
        return 1
    
    # 2. User registration
    if not tester.test_register():
        print("❌ Registration failed, stopping tests")
        return 1
    
    # 3. Get user info
    if not tester.test_get_user_info():
        print("❌ Get user info failed, stopping tests")
        return 1
    
    # 4. Create a question
    question_id = tester.test_create_question()
    if not question_id:
        print("❌ Question creation failed, stopping tests")
        return 1
    
    # 5. Get questions list
    questions = tester.test_get_questions()
    if not questions:
        print("⚠️ No questions found in list")
    
    # 6. Get question details
    if not tester.test_get_question_detail(question_id):
        print("❌ Get question detail failed")
    
    # 7. Create an answer
    answer_id = tester.test_create_answer(question_id)
    if not answer_id:
        print("❌ Answer creation failed")
    
    # 8. Get answers
    answers = tester.test_get_answers(question_id)
    if not answers:
        print("⚠️ No answers found")
    
    # 9. Test voting on question
    if not tester.test_vote_question(question_id, 1):
        print("❌ Question voting failed")
    
    # 10. Test voting on answer (if answer exists)
    if answer_id and not tester.test_vote_answer(answer_id, 1):
        print("❌ Answer voting failed")
    
    # 11. Test search
    search_results = tester.test_search_questions("testing")
    if not search_results:
        print("⚠️ Search returned no results")
    
    # 12. Test AI chat
    if not tester.test_ai_chat():
        print("❌ AI chat failed")
    
    # Print final results
    print("\n" + "=" * 50)
    print(f"📊 Final Results:")
    print(f"   Tests Run: {tester.tests_run}")
    print(f"   Tests Passed: {tester.tests_passed}")
    print(f"   Success Rate: {(tester.tests_passed/tester.tests_run)*100:.1f}%")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed!")
        return 0
    else:
        print(f"⚠️ {tester.tests_run - tester.tests_passed} tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())