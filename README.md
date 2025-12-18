# BoardBrain 🧠

BoardBrain is a Streamlit application designed to process video recordings of HOA board meetings into actionable data. It utilizes FFmpeg for audio processing, AssemblyAI for transcription (with speaker diarization), and OpenAI GPT-4o to extract structured insights like motions and action items.

## Features

### 🧩 HOA-Specific Intelligence
*   **Parliamentarian Mode**:
    *   **Motion Validation**: Automatically checks if motions were "Seconded" before marking them as valid, adhering to Robert's Rules of Order.
    *   **Quorum Monitor**: Upload your bylaws to automatically verify if enough board members are present for a valid vote based on the speaker count.
*   **Financial Impact Analysis**: Detects dollar amounts, bids, and budget discussions to create a "Potential Spend" report, ensuring no financial detail is missed.
*   **Smart Speaker ID**: Uses GPT-4o context clues (e.g., "I agree, Susan") to automatically identify and label speakers in the transcript.

### 📄 Automated Reporting
*   **Instant Minutes Draft**: One-click export to **Microsoft Word (.docx)**. Generates a professional draft including:
    *   Executive Summary
    *   Motions Table (Proposer, Seconder, Outcome)
    *   Action Items (Task, Assignee, Due Date)
*   **Topic & Sentiment Trends**: Visual analytics showing what topics dominated the conversation and the overall sentiment of the board.

### 🤖 Interactive Assistant
*   **Chat with your Meeting**: Ask questions like "What was the final decision on the pool contract?" and get answers with **timestamped citations** linking directly to the audio.
*   **Transcript Search**: instant search with word-level audio synchronization.



## Prerequisites (Windows)

### 1. Install FFmpeg
The application requires **FFmpeg** to extract audio from video files.

**Option A: Using Winget (Recommended)**
Open PowerShell as Administrator and run:
```powershell
winget install "FFmpeg (Essentials Build)"
```
*Restart your terminal after installation.*

**Option B: Manual Installation**
1.  Download the build from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) (choose "ffmpeg-git-full.7z").
2.  Extract the folder (e.g., to `C:\ffmpeg`).
3.  Add `C:\ffmpeg\bin` to your System **PATH** environment variable:
    *   Search for "Edit the system environment variables" in the Start menu.
    *   Click "Environment Variables".
    *   Under "System variables", select "Path" and click "Edit".
    *   Click "New" and paste the path to the `bin` folder.

### 2. Python
Ensure you have Python 3.8+ installed. You can download it from the [Microsoft Store](https://apps.microsoft.com/detail/9pjpw5ldxlz5) or [python.org](https://www.python.org/).

## Installation

1.  Clone the repository or download the source code.
2.  Open **PowerShell** or **Command Prompt** in the project folder.
3.  (Optional) Create and activate a virtual environment:
    ```powershell
    python -m venv venv
    .\venv\Scripts\activate
    ```
4.  Install the required Python packages:
    ```powershell
    pip install -r requirements.txt
    ```

## Configuration

To avoid entering API keys every time you run the app, you can create a `secrets.txt` file in the project root. This is highly recommended for frequent use.

Create a file named `secrets.txt` and add your keys (TOML format):

```toml
ASSEMBLYAI_API_KEY = "your_assemblyai_key_here"
OPENAI_API_KEY = "your_openai_key_here"

# Optional: For saving meeting history to the cloud
SUPABASE_URL = "your_supabase_project_url"
SUPABASE_KEY = "your_supabase_anon_key"
```

## Running the Application

Run the Streamlit app using the following command:

```powershell
streamlit run app.py
```

The application will open in your default web browser (usually at `http://localhost:8501`).

## Usage Guide

1.  **Initialization**:
    *   The app will automatically load keys from `secrets.txt` if present.
    *   Otherwise, enter your **AssemblyAI** and **OpenAI** keys in the sidebar.
    *   **Mock Mode**: If keys are missing, or if you type `dummy`, the app runs in "Mock Mode" for zero-cost testing.

2.  **Processing**:
    *   Upload a video file (MP4, MOV, AVI).
    *   (Optional) **Parliamentarian Mode**: Upload or paste your **Community Bylaws**. This enables the app to check for Quorum and validate motions more strictly.
    *   Click **Process Meeting**.

3.  **Results**:
    *   **Dashboard**: View the Executive Summary, Motions Table, and Action Items.
    *   **Analytics**: Visualize speaking time, topic distribution, and financial impact.
    *   **Export**: Click "Download Word Document" to get a pre-formatted minutes draft.
    *   **Assistant**: Use the sidebar chat to ask questions about the meeting history.
