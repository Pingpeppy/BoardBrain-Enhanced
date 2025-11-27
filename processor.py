import os
import subprocess
import time
import json
import requests
import tempfile
from openai import OpenAI
import platform
from docx import Document
from io import BytesIO

# --- Audio Extraction ---

def get_ffmpeg_command():
    """
    Attempts to locate FFmpeg in the following order:
    1. 'static_ffmpeg' python package (auto-installs binary).
    2. System PATH.
    3. Common Windows installation paths.

    Returns the command (list of strings or string) to run FFmpeg.
    Raises RuntimeError if not found.
    """

    # 1. Try static-ffmpeg (Preferred for auto-install)
    try:
        import static_ffmpeg
        ffmpeg_cmd, _ = static_ffmpeg.run.get_or_fetch_platform_executables_else_raise()
        return ffmpeg_cmd
    except ImportError:
        pass # Not installed, continue to next method
    except Exception:
        pass # Failed to fetch/run, continue

    # 2. Check System PATH
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return "ffmpeg"
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # 3. Check Common Windows Paths (Fallback)
    if platform.system() == "Windows":
        possible_paths = [
            os.path.join(os.getcwd(), "ffmpeg.exe"),
            r"C:\ffmpeg\bin\ffmpeg.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\ffmpeg\bin\ffmpeg.exe"), # Heuristic
            os.path.expandvars(r"%USERPROFILE%\ffmpeg.exe"), # User mentioned default powershell location
        ]

        for path in possible_paths:
            if os.path.exists(path) and os.path.isfile(path):
                return path

    raise RuntimeError(
        "FFmpeg is not installed or not found. "
        "The application attempted to find it in system PATH, common folders, and via 'static-ffmpeg'. "
        "Please ensure FFmpeg is installed and reachable."
    )

def extract_audio(video_path):
    """
    Extracts audio from a video file using FFmpeg.
    Converts to 16kHz mono MP3 to save bandwidth.
    Returns the path to the temporary MP3 file.
    """
    ffmpeg_cmd = get_ffmpeg_command()

    try:
        # Create a temp file for the audio
        # We use delete=False because we need to pass the path to AssemblyAI/other funcs
        # and we will manually clean it up later.
        audio_fd, audio_path = tempfile.mkstemp(suffix=".mp3")
        os.close(audio_fd)

        command = [
            ffmpeg_cmd,
            "-y",  # Overwrite output file if exists
            "-i", video_path,
            "-vn", # Disable video recording
            "-ar", "16000", # Audio sampling rate
            "-ac", "1", # Audio channels (mono)
            "-b:a", "32k", # Bitrate (low is fine for speech)
            audio_path
        ]

        # Run the command
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        return audio_path

    except subprocess.CalledProcessError as e:
        # Clean up if it failed
        if os.path.exists(audio_path):
            os.remove(audio_path)
        raise RuntimeError(f"FFmpeg failed: {e.stderr.decode()}")
    except Exception as e:
        if os.path.exists(audio_path):
            os.remove(audio_path)
        raise e

# --- Transcription (AssemblyAI) ---

MOCK_TRANSCRIPT_RESPONSE = {
    "text": "Speaker A: I call this meeting to order. First item is the approval of last month's minutes. Speaker B: I move to approve. Speaker A: Is there a second? Speaker C: I second. Speaker A: All in favor? [Chorus of Ayes]. Motion carries. Next, the roof repairs. We have a bid for $5,000 from Roofing Co. Speaker B: I think that's too high. I propose we get two more bids by next week. Speaker C: Agreed. I'll take that action item.",
    "utterances": [
        {"speaker": "A", "text": "I call this meeting to order. First item is the approval of last month's minutes.", "start": 0, "end": 5000},
        {"speaker": "B", "text": "I move to approve.", "start": 5000, "end": 7000},
        {"speaker": "A", "text": "Is there a second?", "start": 7000, "end": 9000},
        {"speaker": "C", "text": "I second.", "start": 9000, "end": 11000},
        {"speaker": "A", "text": "All in favor? [Chorus of Ayes]. Motion carries.", "start": 11000, "end": 15000},
        {"speaker": "A", "text": "Next, the roof repairs. We have a bid for $5,000 from Roofing Co.", "start": 15000, "end": 20000},
        {"speaker": "B", "text": "I think that's too high. I propose we get two more bids by next week.", "start": 20000, "end": 25000},
        {"speaker": "C", "text": "Agreed. I'll take that action item.", "start": 25000, "end": 28000}
    ]
}

def transcribe_audio(audio_path, api_key):
    """
    Uploads audio to AssemblyAI and gets a transcript with speaker diarization.
    If api_key is 'dummy' or empty, returns a mock transcript.
    """

    # --- MOCK MODE ---
    if not api_key or api_key.strip().lower() == "dummy":
        time.sleep(2) # Simulate processing time
        return MOCK_TRANSCRIPT_RESPONSE
    # -----------------

    headers = {"authorization": api_key}

    # 1. Upload
    def read_file(filename, chunk_size=5242880):
        with open(filename, 'rb') as _file:
            while True:
                data = _file.read(chunk_size)
                if not data:
                    break
                yield data

    try:
        upload_response = requests.post(
            "https://api.assemblyai.com/v2/upload",
            headers=headers,
            data=read_file(audio_path)
        )
        upload_response.raise_for_status()
        upload_url = upload_response.json()["upload_url"]

        # 2. Request Transcription
        transcript_request = {
            "audio_url": upload_url,
            "speaker_labels": True
        }

        response = requests.post(
            "https://api.assemblyai.com/v2/transcript",
            json=transcript_request,
            headers=headers
        )
        response.raise_for_status()
        transcript_id = response.json()["id"]

        # 3. Poll for results
        polling_endpoint = f"https://api.assemblyai.com/v2/transcript/{transcript_id}"

        while True:
            poll_response = requests.get(polling_endpoint, headers=headers)
            poll_response.raise_for_status()
            poll_result = poll_response.json()

            if poll_result["status"] == "completed":
                return poll_result
            elif poll_result["status"] == "error":
                raise RuntimeError(f"Transcription failed: {poll_result['error']}")

            time.sleep(3) # Wait before polling again

    except Exception as e:
        raise RuntimeError(f"AssemblyAI API Error: {str(e)}")

def format_transcript(transcript_obj):
    """
    Converts the raw transcript object (with utterances) into a readable string.
    Format: Speaker A: [text]
    """
    # Check if we have utterances (diarization enabled)
    if "utterances" in transcript_obj and transcript_obj["utterances"]:
        formatted_text = ""
        for turn in transcript_obj["utterances"]:
            speaker = turn["speaker"]
            text = turn["text"]
            formatted_text += f"Speaker {speaker}: {text}\n"
        return formatted_text
    else:
        # Fallback if no speaker labels
        return transcript_obj.get("text", "")

# --- Intelligence Extraction (OpenAI) ---

MOCK_INTELLIGENCE_RESPONSE = {
    "meeting_date": "2023-10-27",
    "motions": [
        {
            "topic": "Approval of last month's minutes",
            "proposer": "Speaker B",
            "seconder": "Speaker C",
            "vote_outcome": "Passed",
            "status": "Carried"
        }
    ],
    "action_items": [
        {
            "task_description": "Get two more bids for roof repairs",
            "assigned_to": "Speaker C",
            "due_date_inference": "Next week"
        }
    ],
    "summary": "The board approved the previous meeting's minutes. A bid for roof repairs was discussed but deemed too high. It was decided to solicit two additional bids by next week."
}

def extract_intelligence(transcript_text, api_key):
    """
    Extracts structured data from the transcript using OpenAI GPT-4o.
    If api_key is 'dummy' or empty, returns a mock transcript.
    """

    # --- MOCK MODE ---
    if not api_key or api_key.strip().lower() == "dummy":
        # Simulate API latency
        time.sleep(2)
        return MOCK_INTELLIGENCE_RESPONSE
    # -----------------

    client = OpenAI(api_key=api_key)

    prompt = (
        "You are an expert HOA Board Secretary. "
        "Extract the following from the transcript and return ONLY raw JSON: "
        "1. meeting_date (YYYY-MM-DD), "
        "2. motions (list of objects with topic, proposer, seconder, vote_outcome, status), "
        "3. action_items (list of objects with task_description, assigned_to, due_date_inference), "
        "4. summary (text). "
        "If date is not found, use null."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": transcript_text}
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        raise RuntimeError(f"OpenAI API Error: {str(e)}")

# --- Document Generation ---

def generate_word_document(intelligence_data, transcript_text, include_transcript=False):
    """
    Generates a Word document containing the meeting intelligence and optionally the transcript.
    Returns a BytesIO object.
    """
    doc = Document()

    # Title
    meeting_date = intelligence_data.get("meeting_date") or "Unknown Date"
    doc.add_heading(f"Board Meeting Notes - {meeting_date}", 0)

    # Executive Summary
    doc.add_heading("Executive Summary", level=1)
    doc.add_paragraph(intelligence_data.get("summary", "No summary available."))

    # Motions
    doc.add_heading("Motions", level=1)
    motions = intelligence_data.get("motions", [])
    if motions:
        table = doc.add_table(rows=1, cols=5)
        table.style = 'Table Grid'
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = 'Topic'
        hdr_cells[1].text = 'Proposer'
        hdr_cells[2].text = 'Seconder'
        hdr_cells[3].text = 'Outcome'
        hdr_cells[4].text = 'Status'

        for motion in motions:
            row_cells = table.add_row().cells
            row_cells[0].text = str(motion.get("topic", ""))
            row_cells[1].text = str(motion.get("proposer", ""))
            row_cells[2].text = str(motion.get("seconder", ""))
            row_cells[3].text = str(motion.get("vote_outcome", ""))
            row_cells[4].text = str(motion.get("status", ""))
    else:
        doc.add_paragraph("No motions recorded.")

    # Action Items
    doc.add_heading("Action Items", level=1)
    actions = intelligence_data.get("action_items", [])
    if actions:
        table = doc.add_table(rows=1, cols=3)
        table.style = 'Table Grid'
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = 'Task'
        hdr_cells[1].text = 'Assigned To'
        hdr_cells[2].text = 'Due'

        for action in actions:
            row_cells = table.add_row().cells
            row_cells[0].text = str(action.get("task_description", ""))
            row_cells[1].text = str(action.get("assigned_to", ""))
            row_cells[2].text = str(action.get("due_date_inference", ""))
    else:
        doc.add_paragraph("No action items recorded.")

    # Transcript (Optional)
    if include_transcript:
        doc.add_heading("Full Transcript", level=1)
        doc.add_paragraph(transcript_text)

    # Save to buffer
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# --- Chat Functionality ---

def chat_with_meeting(transcript_text, chat_history, user_message, api_key):
    """
    Sends a message to the LLM with the transcript context and chat history.
    Returns the assistant's response text.
    """

    # --- MOCK MODE ---
    if not api_key or api_key.strip().lower() == "dummy":
        time.sleep(1)
        return f"This is a mock response to: '{user_message}' (Mock Mode Enabled)"
    # -----------------

    client = OpenAI(api_key=api_key)

    # Construct messages
    # System prompt
    system_prompt = (
        "You are a helpful assistant analyzing a Board Meeting transcript. "
        "Use the provided transcript to answer the user's questions. "
        "If the answer is not in the transcript, say so."
    )

    messages = [{"role": "system", "content": system_prompt}]

    # Provide transcript context (could be added as a system message or first user message)
    # Adding it as a system context for better adherence
    messages.append({
        "role": "system",
        "content": f"TRANSCRIPT CONTEXT:\n{transcript_text}"
    })

    # Add history
    # chat_history is expected to be list of {"role": "user"|"assistant", "content": "..."}
    # Streamlit chat format: {"role": "user", "content": "msg"}
    # We filter/map it just to be safe if needed, but assuming direct pass-through
    for msg in chat_history:
        messages.append({"role": msg["role"], "content": msg["content"]})

    # Note: We do NOT append user_message explicitly here because it is expected
    # that the caller (app.py) has already appended the latest user message to chat_history.

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error communicating with OpenAI: {str(e)}"
