# BoardBrain 🧠

BoardBrain is a Streamlit application designed to process video recordings of HOA board meetings into actionable data. It utilizes FFmpeg for audio processing, AssemblyAI for transcription (with speaker diarization), and OpenAI GPT-4o to extract structured insights like motions and action items.

## Features

*   **Video Processing**: Extracts audio from MP4, MOV, and AVI files.
*   **Transcription**: Uses AssemblyAI to provide speaker-labeled transcripts.
*   **Intelligence**: Uses OpenAI GPT-4o to extract:
    *   Executive Summary
    *   Motions (Topic, Proposer, Vote Outcome)
    *   Action Items (Task, Assignee, Due Date)
*   **Mock Mode**: Built-in testing mode to simulate the pipeline without valid API keys.

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

## Running the Application

Run the Streamlit app using the following command:

```powershell
streamlit run app.py
```

The application will open in your default web browser (usually at `http://localhost:8501`).

## Usage Guide

1.  **API Keys**:
    *   On the sidebar, you will be asked for an **AssemblyAI API Key** and an **OpenAI API Key**.
    *   If you have them, enter them to use the real services.
    *   **Mock Mode**: If you do not have keys, or if you type `dummy` into the fields, the app will run in "Mock Mode". This allows you to test the UI and flow using sample data without incurring API costs.

2.  **Processing**:
    *   Upload a video file (MP4, MOV, AVI).
    *   Click **Process Meeting**.
    *   Watch the status logs as the app extracts audio, transcribes, and generates insights.

3.  **Results**:
    *   **Insights Tab**: View the Executive Summary, Motions table, and Action Items table.
    *   **Transcript Tab**: Read the full transcript with speaker labels.
