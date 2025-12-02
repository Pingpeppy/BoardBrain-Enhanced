
import os
import shutil
import time
from playwright.sync_api import sync_playwright, expect

def verify_chat_above_settings():
    """
    Verifies that the Chat Assistant is located above the Settings in the sidebar.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        print("Navigating to app...")
        page.goto("http://localhost:8501")

        # Wait for load
        page.wait_for_selector("text=BoardBrain")

        # 2. Enable Mock Mode
        print("Enabling Mock Mode...")
        mock_mode_label = page.get_by_text("Enable Mock Mode")
        mock_mode_label.click()

        # Wait a moment for rerun
        time.sleep(2)

        # 3. Upload a Dummy File
        print("Uploading dummy video...")

        # Create a dummy video file
        dummy_video_path = "/tmp/dummy_video.mp4"
        with open(dummy_video_path, "wb") as f:
            f.write(b"fake video content")

        page.set_input_files("input[type='file']", dummy_video_path)

        # Wait for file to be processed/uploaded by Streamlit
        time.sleep(3)

        # 4. Click "Process Meeting"
        print("Clicking Process Meeting...")
        # Be more specific with locator
        process_button = page.get_by_role("button", name="Process Meeting")
        process_button.click()

        # 5. Wait for Results
        # Processing might take a few seconds
        print("Waiting for results...")
        try:
            expect(page.get_by_text("Meeting Processed Successfully!")).to_be_visible(timeout=20000)
        except Exception:
            # If failed, take screenshot for debug
            page.screenshot(path="verification/debug_failed_process.png")
            raise

        # 6. Verify Sidebar Order
        print("Verifying Sidebar Order...")
        sidebar = page.locator('section[data-testid="stSidebar"]')

        # We need to find the Chat Header and the Settings Header
        chat_header = sidebar.get_by_text("💬 Assistant")
        settings_header = sidebar.get_by_text("⚙️ Settings")

        expect(chat_header).to_be_visible()
        expect(settings_header).to_be_visible()

        # Get bounding boxes to compare Y positions
        chat_box = chat_header.bounding_box()
        settings_box = settings_header.bounding_box()

        print(f"Chat Y: {chat_box['y']}")
        print(f"Settings Y: {settings_box['y']}")

        if chat_box['y'] < settings_box['y']:
            print("SUCCESS: Chat is above Settings.")
        else:
            raise AssertionError("FAILURE: Chat is NOT above Settings.")

        # 7. Take Screenshot
        print("Taking verification screenshot...")
        page.screenshot(path="verification/verification_order.png")

        print("Verification Successful!")
        browser.close()

if __name__ == "__main__":
    verify_chat_above_settings()
