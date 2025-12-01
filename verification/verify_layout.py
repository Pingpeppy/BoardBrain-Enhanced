
import os
import shutil
import time
from playwright.sync_api import sync_playwright, expect

def verify_chat_in_sidebar():
    """
    Verifies that the Chat Assistant is located in the sidebar on the Results page.
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
        # Check if the "Process Meeting" button is enabled?
        # Sometimes upload takes time.
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

        # 6. Verify Chat in Sidebar
        print("Verifying Chat location...")
        sidebar = page.locator('section[data-testid="stSidebar"]')

        # Check if "💬 Assistant" text is inside the sidebar locator
        assistant_header = sidebar.get_by_text("💬 Assistant")
        expect(assistant_header).to_be_visible()

        # Check if chat input is in sidebar
        chat_input_label = sidebar.get_by_label("Ask a question...")
        expect(chat_input_label).to_be_visible()

        # 7. Take Screenshot
        print("Taking verification screenshot...")
        page.screenshot(path="verification/verification.png")

        print("Verification Successful!")
        browser.close()

if __name__ == "__main__":
    verify_chat_in_sidebar()
