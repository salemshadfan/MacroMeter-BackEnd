import os
from dotenv import load_dotenv

load_dotenv() 

import unittest
from unittest.mock import patch, MagicMock
import json
from app import app  

class AppTestCase(unittest.TestCase):

    def setUp(self):
        """Set up a test client."""
        self.app = app.test_client()
        self.app.testing = True

    @patch("app.get_db_connection")
    def test_signup_success(self, mock_db_conn):
        """Test user signup with valid data."""
        mock_cursor = MagicMock()
        mock_db_conn.return_value.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None  # Simulate no existing user
        mock_cursor.fetchone.side_effect = [(1, "testuser", "test@example.com")]  # Mock new user creation
        mock_db_conn.return_value.commit.return_value = None

        response = self.app.post("/signup", json={
            "username": "newuser",  # Ensure a new user
            "email": "new@example.com",  # Ensure unique email
            "password": "password123"
        })

        print("Signup Response:", response.get_json())  # Debugging
        self.assertEqual(response.status_code, 201)  # Expected 201 Created



    @patch("app.get_db_connection")
    def test_signup_existing_user(self, mock_db_conn):
        """Test signup when user already exists."""
        mock_cursor = MagicMock()
        mock_db_conn.return_value.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (1,)  # Existing user

        response = self.app.post("/signup", json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123"
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn("User already exists", response.get_data(as_text=True))

    @patch("app.get_db_connection")
    def test_login_success(self, mock_db_conn):
        """Test login with correct credentials."""
        mock_cursor = MagicMock()
        mock_db_conn.return_value.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (1, "test@example.com", "$2b$12$E.bQJYmUJYwN3RuX")  # Mock hashed password
        with patch("bcrypt.checkpw", return_value=True):  # Mock bcrypt check
            with patch("app.create_access_token", return_value="mock_token"):  # Mock JWT
                response = self.app.post("/login", json={
                    "email": "test@example.com",
                    "password": "password123"
                })

        self.assertEqual(response.status_code, 200)
        self.assertIn("mock_token", response.get_data(as_text=True))

    @patch("app.get_db_connection")
    def test_login_invalid_password(self, mock_db_conn):
        """Test login with incorrect password."""
        mock_cursor = MagicMock()
        mock_db_conn.return_value.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (1, "test@example.com", "$2b$12$E.bQJYmUJYwN3RuX")
        with patch("bcrypt.checkpw", return_value=False):  # Password check fails
            response = self.app.post("/login", json={
                "email": "test@example.com",
                "password": "wrongpassword"
            })

        self.assertEqual(response.status_code, 401)
        self.assertIn("Invalid email or password", response.get_data(as_text=True))

    @patch("app.get_jwt_identity", return_value=1)  # Ensure valid user
    @patch("app.get_db_connection")
    def test_wipe_history(self, mock_db_conn, mock_jwt):
        """Test history wipe."""
        mock_cursor = MagicMock()
        mock_db_conn.return_value.cursor.return_value = mock_cursor
        mock_db_conn.return_value.commit.return_value = None

        response = self.app.get("/wipe", headers={"Authorization": "Bearer mock_token"})  # Ensure valid token

        print("Wipe History Response:", response.get_json())  # Debugging
        self.assertEqual(response.status_code, 200)

    

    @patch("app.request")
    @patch("app.api.generate_gpt_prompt", return_value="mock prompt")
    @patch("app.api.GPT_Analyze", return_value="success: {\"name\": \"Pizza\", \"calories\": 300}")
    @patch("app.api.convert_to_json", return_value={"name": "Pizza", "calories": 300})
    @patch("app.jwt_required", lambda x: x)  # Mock authentication
    def test_analyze_image(self, mock_request, mock_gpt_prompt, mock_gpt_analyze, mock_convert_json):
        """Test image analysis with AI API mocking."""
        with app.test_request_context():  # Ensure request context exists
            mock_file = MagicMock()
            mock_file.filename = "test.jpg"
            mock_request.files = {"image": mock_file}
            
            response = self.app.post("/api/analyze-image", headers={"Authorization": "Bearer test_token"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("Pizza", response.get_data(as_text=True))



    @patch("app.get_db_connection")
    @patch("app.send_reset_email")
    def test_reset_password(self, mock_send_email, mock_db_conn):
        """Test password reset request."""
        mock_cursor = MagicMock()
        mock_db_conn.return_value.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (1, "test@example.com")

        response = self.app.post("/reset-link", json={"email": "test@example.com"})

        self.assertEqual(response.status_code, 200)
        mock_send_email.assert_called_once()

    @patch("app.get_jwt_identity", return_value=1)  # Ensure valid user
    @patch("app.get_db_connection")
    def test_history_fetch(self, mock_db_conn, mock_jwt):
        """Test fetching user history."""
        mock_cursor = MagicMock()
        mock_db_conn.return_value.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [("history_entry_1",), ("history_entry_2",)]

        response = self.app.get("/history", headers={"Authorization": "Bearer mock_token"})  # Ensure valid token

        print("History Fetch Response:", response.get_json())  # Debugging
        self.assertEqual(response.status_code, 200)



if __name__ == "__main__":
    unittest.main()
