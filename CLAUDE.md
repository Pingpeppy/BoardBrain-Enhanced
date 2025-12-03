# CLAUDE.md - BoardBrain AI Assistant Guide

## Project Overview

**BoardBrain** is a Streamlit-based web application that processes HOA (Homeowners Association) board meeting videos into actionable data. The application extracts audio from video files, transcribes them with speaker diarization, and uses AI to extract structured insights like motions, action items, and executive summaries.

### Core Purpose
- Transform video recordings of HOA board meetings into structured, searchable data
- Extract motions, action items, and meeting summaries automatically
- Validate meeting compliance with parliamentary procedures (Robert's Rules of Order)
- Provide an interactive chat interface to query meeting content

---

## Codebase Structure

### Repository Layout
```
BoardBrain/
├── app.py                      # Main Streamlit UI application (808 lines)
├── processor.py                # Core business logic & API integrations (686 lines)
├── requirements.txt            # Python dependencies
├── packages.txt                # System dependencies (FFmpeg)
├── README.md                   # User-facing documentation
├── .streamlit/
│   └── secrets.toml           # API keys configuration (gitignored)
├── tests/
│   └── test_processor.py      # Unit tests for processor functions
├── verification/
│   ├── verify_layout.py       # Playwright E2E tests
│   └── *.png                  # Verification screenshots
└── .gitignore                 # Git ignore patterns
```

### File Responsibilities

#### **app.py** - User Interface Layer
- **Purpose**: Streamlit UI, session state management, user interactions
- **Key Sections**:
  - Page configuration and dark mode styling
  - Sidebar layout (Chat Assistant + Settings)
  - Two-step workflow: Upload → Results
  - Three main tabs: Dashboard, Analytics, Transcript
  - Interactive audio-synced transcript viewer with custom HTML/JS/CSS
  - Speaker name editing and re-processing workflow
  - Export functionality (Word documents)

#### **processor.py** - Business Logic Layer
- **Purpose**: Audio processing, API integrations, data transformation
- **Key Functions**:
  - `extract_audio()`: FFmpeg-based audio extraction from video
  - `transcribe_audio()`: AssemblyAI integration with speaker diarization
  - `extract_intelligence()`: OpenAI GPT-4o structured data extraction
  - `format_transcript()`: Convert API responses to readable text
  - `calculate_speaking_time()`: Analytics on speaker participation
  - `chat_with_meeting()`: Context-aware chat assistant
  - `suggest_speaker_names()`: AI-powered speaker identification
  - `generate_word_document()`: Export meeting notes to DOCX

#### **tests/test_processor.py**
- **Purpose**: Unit tests for processor functions
- **Coverage**: Currently focused on `calculate_speaking_time()` edge cases
- **Framework**: Python's built-in `unittest`

#### **verification/verify_layout.py**
- **Purpose**: End-to-end UI testing with Playwright
- **Tests**: Sidebar layout verification, mock mode workflow

---

## Technology Stack

### Core Framework
- **Streamlit** (Latest): Web application framework
  - Session state for multi-step workflows
  - Component customization with HTML/JS
  - Dark mode styling

### External APIs
- **AssemblyAI**: Audio transcription with speaker diarization
  - Endpoint: `https://api.assemblyai.com/v2/`
  - Features: Upload → Transcribe → Poll for results
  - Mock mode available (keyword: "dummy")

- **OpenAI GPT-4o**: Structured data extraction and chat
  - Model: `gpt-4o`
  - JSON mode for structured extraction
  - Chat completions for assistant feature

### Dependencies
```
streamlit           # Web framework
pandas              # Data manipulation
requests            # HTTP client for AssemblyAI
openai              # OpenAI API client
static-ffmpeg       # Bundled FFmpeg binary
python-docx         # Word document generation
pypdf               # PDF parsing (for bylaws upload)
altair              # Data visualization
```

### System Requirements
- **FFmpeg**: Required for audio extraction from video
  - Packaged via `static-ffmpeg` (preferred)
  - Falls back to system PATH or common install locations
  - Specified in `packages.txt` for Streamlit Cloud deployment

---

## Development Workflows

### Standard Feature Development
1. **Create feature branch** from main
   - Naming pattern: `feature/{description}` or `fix/{description}`
   - Examples: `feature/dark-mode-dashboard`, `fix/ffmpeg-cloud-deploy`

2. **Development cycle**:
   - Make changes in either `app.py` (UI) or `processor.py` (logic)
   - Test locally: `streamlit run app.py`
   - Use Mock Mode for testing without API keys
   - Write unit tests in `tests/` if adding new processor functions
   - Write E2E tests in `verification/` for UI changes

3. **Pull Request workflow**:
   - Recent PRs show clear, descriptive titles
   - Merges to main branch via GitHub PR
   - No squashing pattern observed (merge commits preserved)

### Testing Strategy

#### Mock Mode
- **Purpose**: Test application flow without consuming API credits
- **Activation**: Enter "dummy" as API key OR check "Enable Mock Mode"
- **Behavior**:
  - Audio extraction skipped (generates dummy audio file)
  - Transcription returns `MOCK_TRANSCRIPT_RESPONSE` from `processor.py:105`
  - Intelligence returns `MOCK_INTELLIGENCE_RESPONSE` from `processor.py:375`
  - Chat returns simple echo response

#### Unit Testing
```bash
# Run tests from project root
python -m unittest tests/test_processor.py

# Or use pytest if available
pytest tests/
```

#### E2E Testing
```bash
# Requires Streamlit app running on localhost:8501
streamlit run app.py &
python verification/verify_layout.py
```

---

## Key Design Patterns & Conventions

### Architecture Principles

1. **Separation of Concerns**
   - **UI Logic** (`app.py`): Streamlit-specific code, user interactions, styling
   - **Business Logic** (`processor.py`): Pure Python functions, API calls, data transformations
   - **Rule**: Never put Streamlit code in `processor.py`, never put complex logic in `app.py`

2. **Session State Management**
   - All workflow state stored in `st.session_state`
   - Key state variables:
     ```python
     st.session_state.step                    # 'upload' or 'results'
     st.session_state.processing_complete     # Boolean
     st.session_state.intelligence_data       # Extracted meeting data (dict)
     st.session_state.formatted_transcript    # Readable transcript (str)
     st.session_state.raw_transcript          # API response with utterances (dict)
     st.session_state.audio_path              # Path to extracted audio (str)
     st.session_state.chat_history            # List of chat messages
     st.session_state.bylaws_text             # Uploaded bylaws content (str)
     st.session_state.speaker_suggestions     # AI-suggested speaker names (dict)
     ```

3. **Error Handling**
   - Try/catch blocks around API calls and file operations
   - Always clean up temporary files on error
   - User-friendly error messages via `st.error()`

4. **Mock Data Pattern**
   - All API-calling functions check for "dummy" key first
   - Mock responses defined as module-level constants
   - Simulate API latency with `time.sleep()` for realistic testing

### Code Style Conventions

1. **Function Naming**
   - Snake_case for all functions
   - Descriptive names indicating action: `extract_audio()`, `format_transcript()`
   - Boolean-returning functions: `calculate_speaking_time()` (returns dict/data)

2. **Docstrings**
   - Multi-line docstrings for public functions
   - Include purpose, parameters, and return values
   - Example:
     ```python
     def extract_audio(video_path):
         """
         Extracts audio from a video file using FFmpeg.
         Converts to 16kHz mono MP3 to save bandwidth.
         Returns the path to the temporary MP3 file.
         """
     ```

3. **Dark Mode Styling**
   - All custom HTML/CSS uses dark background colors
   - Primary color: `#0068c9` (Streamlit blue)
   - Background: `#0e1117`
   - Text: `#fafafa`
   - Borders: `#333`, `#444`

4. **File Cleanup**
   - Always use `tempfile` module for temporary files
   - Delete=False when creating files that need to persist between function calls
   - Manual cleanup in try/finally or exception handlers
   - Store paths in session state for cleanup on new upload

---

## Common Development Tasks

### Adding a New API Integration

1. **Add mock response** to `processor.py`:
   ```python
   MOCK_NEW_FEATURE_RESPONSE = { ... }
   ```

2. **Create function** with mock mode check:
   ```python
   def new_feature(data, api_key):
       if not api_key or api_key.strip().lower() == "dummy":
           time.sleep(1)
           return MOCK_NEW_FEATURE_RESPONSE

       # Real API call here
       client = SomeAPI(api_key=api_key)
       response = client.do_something(data)
       return response
   ```

3. **Add UI controls** in `app.py`:
   - Input fields in sidebar if needed
   - Call function in processing workflow
   - Display results in appropriate tab

4. **Update session state** if data needs to persist

### Adding a New UI Tab

1. **Modify tab creation** in `app.py:295`:
   ```python
   tab_dashboard, tab_analytics, tab_transcript, tab_new = st.tabs([
       "📊 Dashboard", "📈 Analytics", "📜 Full Transcript", "🆕 New Feature"
   ])
   ```

2. **Create tab content**:
   ```python
   with tab_new:
       st.subheader("New Feature Title")
       # Add components here
   ```

3. **Access data** from session state:
   ```python
   data = st.session_state.intelligence_data
   transcript = st.session_state.formatted_transcript
   ```

### Modifying Intelligence Extraction

1. **Update prompt** in `processor.py:extract_intelligence()` (line 457)
2. **Modify expected JSON structure** in docstring
3. **Update mock response** `MOCK_INTELLIGENCE_RESPONSE` to match new structure
4. **Update UI** in `app.py` to display new fields
5. **Test both mock and real modes**

### Adding New Analytics Visualizations

1. **Create data extraction function** in `processor.py`:
   ```python
   def calculate_new_metric(transcript_obj):
       # Process data
       return metric_data
   ```

2. **Add to Analytics tab** in `app.py`:
   ```python
   with tab_analytics:
       # ... existing code ...

       st.markdown("##### 📊 New Metric")
       metric_data = processor.calculate_new_metric(st.session_state.raw_transcript)

       # Create Altair chart
       df = pd.DataFrame(metric_data)
       chart = alt.Chart(df).mark_bar().encode(...)
       st.altair_chart(chart, use_container_width=True)
   ```

3. **Use Altair** for consistency with existing charts
4. **Follow dark mode color scheme**

---

## Important Gotchas & Edge Cases

### FFmpeg Handling
- **Issue**: FFmpeg may not be in PATH on some systems
- **Solution**: `get_ffmpeg_command()` tries multiple fallback locations
- **Cloud Deployment**: Ensure `packages.txt` contains `ffmpeg`
- **Testing**: Mock mode skips FFmpeg entirely

### Temporary File Management
- **Issue**: Temp files can accumulate if not cleaned up
- **Pattern**: Always store paths in session state for cleanup
- **Cleanup Points**:
  - On new upload (line 203-204 in `app.py`)
  - On error (try/finally blocks)
  - Before app shutdown (handled by OS for tempfile)

### Session State Rerun Behavior
- **Issue**: Streamlit reruns entire script on interaction
- **Solution**: Check `if "key" not in st.session_state:` before initialization
- **Warning**: Don't rely on module-level variables persisting between reruns

### Speaker Label Consistency
- **Issue**: Speaker labels can change when re-transcribing
- **Solution**: Speaker name editing feature allows manual correction
- **Flow**: Edit → Reprocess → Update intelligence data
- **State**: Store both `raw_transcript` (mutable) and `formatted_transcript` (derived)

### API Rate Limits
- **AssemblyAI**: Polling interval is 3 seconds (line 301)
- **OpenAI**: No explicit rate limiting, but use reasonable defaults
- **Mock Mode**: Use for rapid iteration without hitting rate limits

### Transcript Format Variations
- **With Utterances**: Full speaker diarization, word-level timestamps
- **Without Utterances**: Plain text fallback
- **Handling**: Always check `if "utterances" in transcript_obj:` before accessing

---

## Recent Development History

### Latest Features (from git log)
1. **Layout Fix**: Chat moved to sidebar above settings (PR #17)
2. **Dark Mode Dashboard**: Analytics tab with Altair charts (PR #16)
3. **Auto Speaker Identification**: AI-suggested speaker names (PR #15)
4. **Speaker Renaming**: Edit speakers and re-process intelligence (PR #13)
5. **Secrets Management**: `st.secrets` for API keys (PR #12)
6. **Parliamentarian Mode**: Quorum validation, motion seconding rules (PRs #10-11)
7. **Cloud Deployment**: FFmpeg via `packages.txt` (PR #8)

### Development Velocity
- Active development with frequent PRs
- Feature-focused commits (not bug-heavy)
- UI/UX improvements alongside core features
- Testing infrastructure added recently (verification/)

---

## AI Assistant Guidelines

### When Making Changes

1. **Understand the two-layer architecture**
   - UI changes go in `app.py`
   - Logic changes go in `processor.py`
   - Never mix the two

2. **Always implement mock mode**
   - Users rely on mock mode for testing
   - Add mock responses for new API calls
   - Simulate realistic delays

3. **Preserve dark mode styling**
   - Use existing color variables
   - Test custom HTML/CSS in dark backgrounds
   - Match existing component styles

4. **Update both code paths**
   - If modifying intelligence extraction, update mock response too
   - If changing transcript format, update all consumers
   - If adding session state, initialize properly

5. **Test the full workflow**
   - Upload → Process → Results → Export
   - Try both mock and real API modes (if keys available)
   - Check speaker editing and re-processing
   - Verify chat assistant works with new data

6. **Clean up temporary files**
   - Use tempfile module
   - Store paths for cleanup
   - Handle errors gracefully

### When Reviewing Code

1. **Check session state management**
   - Is state properly initialized?
   - Are reruns handled correctly?
   - Is cleanup happening on new uploads?

2. **Verify API error handling**
   - Try/catch around API calls?
   - User-friendly error messages?
   - Fallback to mock mode on invalid keys?

3. **Confirm dark mode compatibility**
   - Custom CSS uses dark colors?
   - Text contrast sufficient?
   - Charts styled appropriately?

4. **Review data flow**
   - Raw transcript → Formatted transcript → Intelligence
   - Changes propagate correctly?
   - Re-processing updates all derived data?

### When Debugging Issues

1. **Check Mock Mode First**
   - Does it work in mock mode?
   - If yes, issue is with API integration
   - If no, issue is with core logic

2. **Inspect Session State**
   - Add `st.write(st.session_state)` temporarily
   - Check for unexpected None values
   - Verify state persistence across reruns

3. **Review Browser Console**
   - For custom HTML/JS components
   - Check for JavaScript errors
   - Verify data is reaching the frontend

4. **Test Incrementally**
   - Isolate functions in `processor.py`
   - Test with mock data in Python REPL
   - Add to app UI once working

### Common Questions

**Q: Where do I add a new feature?**
- UI components → `app.py`
- Data processing → `processor.py`
- Tests → `tests/` (unit) or `verification/` (E2E)

**Q: How do I handle new API keys?**
- Add to `.streamlit/secrets.toml` (not in git)
- Add input field in sidebar settings (app.py:42)
- Pass to processor functions as parameter

**Q: How do I modify the intelligence extraction prompt?**
- Edit `processor.py:extract_intelligence()` function
- Update the `prompt` string (line 457)
- Update `MOCK_INTELLIGENCE_RESPONSE` to match new structure
- Update UI in `app.py` to display new fields

**Q: How do I add a new analytics chart?**
- Create data function in `processor.py`
- Call it in Analytics tab (app.py:378)
- Use Altair for charting
- Follow existing color scheme

**Q: Why isn't my session state persisting?**
- Check initialization: `if "key" not in st.session_state:`
- Verify it's set before rerun: `st.rerun()`
- Don't rely on module-level variables

**Q: How do I test without API keys?**
- Enable Mock Mode in sidebar
- OR enter "dummy" as API key
- Mock responses defined in `processor.py`

---

## API Reference

### Processor Functions (processor.py)

#### Audio Processing
```python
get_ffmpeg_command() -> str
    # Returns path to FFmpeg executable

extract_audio(video_path: str) -> str
    # Returns path to extracted audio file (MP3, 16kHz mono)
```

#### Transcription
```python
transcribe_audio(audio_path: str, api_key: str) -> dict
    # Returns AssemblyAI transcript object with utterances
    # Mock mode: api_key = "dummy"

format_transcript(transcript_obj: dict) -> str
    # Converts utterances to readable text

format_transcript_with_timestamps(transcript_obj: dict) -> str
    # Adds [MM:SS] timestamps to each utterance

calculate_speaking_time(transcript_obj: dict) -> dict[str, int]
    # Returns {speaker: milliseconds} mapping
```

#### Intelligence Extraction
```python
extract_intelligence(
    transcript_text: str,
    api_key: str,
    bylaws_text: str = None,
    speakers_count: int = None
) -> dict
    # Returns structured data:
    # {
    #   "meeting_date": "YYYY-MM-DD",
    #   "motions": [...],
    #   "action_items": [...],
    #   "summary": "...",
    #   "sentiment_analysis": {...},
    #   "topic_trends": [...]
    # }

suggest_speaker_names(transcript_text: str, api_key: str) -> dict[str, str]
    # Returns {"Speaker A": "John Doe", ...}

read_file_content(file_obj, filename: str) -> str
    # Supports .txt, .pdf, .docx
```

#### Chat Assistant
```python
chat_with_meeting(
    transcript_text: str,
    chat_history: list[dict],
    user_message: str,
    api_key: str,
    intelligence_data: dict = None
) -> str
    # Returns assistant response
```

#### Export
```python
generate_word_document(
    intelligence_data: dict,
    transcript_text: str,
    include_transcript: bool = False
) -> BytesIO
    # Returns Word document buffer
```

### Session State Keys (app.py)

```python
st.session_state.step                    # str: 'upload' | 'results'
st.session_state.processing_complete     # bool
st.session_state.intelligence_data       # dict | None
st.session_state.formatted_transcript    # str
st.session_state.raw_transcript          # dict
st.session_state.audio_path              # str | None
st.session_state.bylaws_text             # str
st.session_state.chat_history            # list[dict]
st.session_state.speaker_suggestions     # dict[str, str]
```

---

## Deployment Notes

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Configure secrets (create file if not exists)
mkdir -p .streamlit
cat > .streamlit/secrets.toml << EOF
ASSEMBLYAI_API_KEY = "your-key-here"
OPENAI_API_KEY = "your-key-here"
EOF

# Run app
streamlit run app.py
```

### Streamlit Cloud Deployment
- **Repository**: Auto-deploy from GitHub repo
- **Secrets**: Configure in Streamlit Cloud dashboard (not in repo)
- **System Packages**: `packages.txt` → installs FFmpeg
- **Python Packages**: `requirements.txt` → automatic
- **Entry Point**: `app.py`

### FFmpeg on Cloud
- Streamlit Cloud supports `packages.txt` for apt packages
- `packages.txt` contains: `ffmpeg`
- Application uses `static-ffmpeg` as primary method
- Falls back to system FFmpeg installed via packages.txt

---

## Future Considerations

### Potential Improvements
1. **Database Storage**: Store historical meetings for trend analysis
2. **User Authentication**: Multi-user support with separate workspaces
3. **Real-time Transcription**: Live meeting transcription during events
4. **Advanced Analytics**: Cross-meeting analytics, attendance tracking
5. **Calendar Integration**: Link meetings to calendar events
6. **Email Notifications**: Auto-send summaries to stakeholders
7. **Mobile Optimization**: Responsive design for tablet viewing
8. **Batch Processing**: Upload multiple meetings at once

### Technical Debt
1. **Test Coverage**: Expand unit tests beyond `calculate_speaking_time()`
2. **Error Logging**: Structured logging instead of print/st.error
3. **Configuration**: Externalize magic numbers and prompts
4. **Type Hints**: Add type annotations throughout
5. **Documentation**: Add inline comments for complex logic
6. **Performance**: Cache API responses more aggressively

---

## Contact & Support

For issues, feature requests, or questions:
- **GitHub Issues**: Preferred for bug reports and features
- **README**: User-facing documentation for setup and usage
- **This File**: Developer documentation for AI assistants and contributors

---

*Last Updated: 2025-12-03*
*Auto-generated by Claude Code for AI assistant guidance*
