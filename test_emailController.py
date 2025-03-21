import unittest
from unittest.mock import patch, MagicMock
from controllers import emailController
import email


class TestSendResetEmail(unittest.TestCase):

    @patch("controllers.emailController.smtplib.SMTP")
    @patch.dict("os.environ", {
        "SMTP_SERVER": "smtp.test.com",
        "SMTP_PORT": "587",
        "SMTP_USER": "test@test.com",
        "SMTP_PASSWORD": "testpassword"
    })
    def test_send_reset_email_success(self, mock_smtp):
        to_email = "user@example.com"
        reset_link = "https://example.com/reset?token=123"

        mock_server_instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server_instance

        emailController.send_reset_email(to_email, reset_link)

        mock_smtp.assert_called_with("smtp.test.com", 587)
        mock_server_instance.starttls.assert_called_once()
        mock_server_instance.login.assert_called_once_with("test@test.com", "testpassword")
        mock_server_instance.sendmail.assert_called_once()
        args, _ = mock_server_instance.sendmail.call_args
        self.assertIn(to_email, args)

        # Parse MIME email content
        msg = email.message_from_string(args[2])
        payload = msg.get_payload()[0]  # It's a MIMEMultipart with one part (HTML)
        html = payload.get_payload(decode=True).decode()

        # Assert something from the actual HTML content
        self.assertIn("Reset Password", html)
        self.assertIn("https://example.com/reset?token=123", html)

    @patch.dict("os.environ", {}, clear=True)
    def test_missing_email_config_raises_exception(self):
        with self.assertRaises(Exception) as context:
            emailController.send_reset_email("user@example.com", "http://example.com")
        self.assertIn("Email configuration is incomplete", str(context.exception))


if __name__ == "__main__":
    unittest.main()
