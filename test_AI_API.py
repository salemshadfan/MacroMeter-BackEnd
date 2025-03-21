import unittest
from unittest.mock import patch, MagicMock
import base64
import json
import AI_API  

class TestFoodAnalyzer(unittest.TestCase):

    def test_encode_image_to_base64(self):
        # Create a sample image file
        with open("test_image.jpg", "wb") as f:
            f.write(b"test image content")

        encoded = food_analyzer.encode_image_to_base64("test_image.jpg")
        self.assertEqual(encoded, base64.b64encode(b"test image content").decode("utf-8"))

    def test_decode_base64_to_bytes(self):
        encoded = base64.b64encode(b"sample data").decode("utf-8")
        result = food_analyzer.decode_base64_to_bytes(encoded)
        self.assertEqual(result, b"sample data")

    @patch("food_analyzer.service_pb2_grpc.V2Stub")
    @patch("food_analyzer.ClarifaiChannel.get_grpc_channel")
    def test_analyze_image(self, mock_get_channel, mock_stub):
        mock_stub_instance = MagicMock()
        mock_stub.return_value = mock_stub_instance

        mock_output = MagicMock()
        mock_output.data.concepts = []

        mock_response = MagicMock()
        mock_response.status.code = 10000  # status_code_pb2.SUCCESS
        mock_response.outputs = [mock_output]

        mock_stub_instance.PostModelOutputs.return_value = mock_response

        fake_base64 = base64.b64encode(b"dummy").decode("utf-8")
        result = food_analyzer.analyze_image(fake_base64)

        self.assertEqual(result, mock_output)

    @patch("food_analyzer.client.chat.completions.create")
    def test_gpt_analyze_success(self, mock_create):
        mock_create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="success:\n{\n\"name\": \"Salad\",\n\"calories\": 250,\n\"carbohydrates\": 20,\n\"protein\": 5,\n\"fat\": 10\n}"))]
        )

        result = food_analyzer.GPT_Analyze("describe image", "base64data")
        self.assertIn("success:", result)

    def test_convert_to_json_valid(self):
        string = """
        success:
        {
            "name": "Pizza",
            "calories": 300,
            "carbohydrates": 33,
            "protein": 12,
            "fat": 15
        }
        """
        result = food_analyzer.convert_to_json(string)
        self.assertEqual(result["name"], "Pizza")
        self.assertEqual(result["calories"], 300)

    def test_convert_to_json_invalid(self):
        string = "some string without JSON"
        result = food_analyzer.convert_to_json(string)
        self.assertEqual(result, "No JSON found in the string.")

if __name__ == "__main__":
    unittest.main()
