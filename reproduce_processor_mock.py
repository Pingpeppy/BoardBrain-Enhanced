import processor
import json

def test_mock_output():
    print("Testing Mock Output from processor.extract_intelligence...")
    # Call with 'dummy' key to trigger mock mode
    result = processor.extract_intelligence("dummy transcript", "dummy")

    print("\nResult Keys:", result.keys())

    expected_keys = ["meeting_date", "motions", "action_items", "summary", "sentiment_analysis", "topic_trends"]
    missing = [k for k in expected_keys if k not in result]

    if missing:
        print(f"FAILED: Missing keys: {missing}")
    else:
        print("SUCCESS: All expected keys present.")

    print("\nFull Result:\n", json.dumps(result, indent=2))

if __name__ == "__main__":
    test_mock_output()
