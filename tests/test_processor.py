
import unittest
import processor

class TestProcessor(unittest.TestCase):
    def test_calculate_speaking_time_simple(self):
        transcript_obj = {
            "utterances": [
                {"speaker": "Alice", "start": 0, "end": 1000},
                {"speaker": "Bob", "start": 1000, "end": 2000},
                {"speaker": "Alice", "start": 2000, "end": 3500},
            ]
        }
        # Alice: 1000 + 1500 = 2500
        # Bob: 1000
        result = processor.calculate_speaking_time(transcript_obj)
        self.assertEqual(result["Alice"], 2500)
        self.assertEqual(result["Bob"], 1000)

    def test_calculate_speaking_time_no_utterances(self):
        transcript_obj = {"text": "Just text"}
        result = processor.calculate_speaking_time(transcript_obj)
        self.assertEqual(result, {})

    def test_calculate_speaking_time_empty(self):
        transcript_obj = {}
        result = processor.calculate_speaking_time(transcript_obj)
        self.assertEqual(result, {})

    def test_calculate_speaking_time_negative_duration(self):
        transcript_obj = {
            "utterances": [
                {"speaker": "Alice", "start": 1000, "end": 500} # Invalid
            ]
        }
        result = processor.calculate_speaking_time(transcript_obj)
        self.assertEqual(result["Alice"], 0)

if __name__ == "__main__":
    unittest.main()
