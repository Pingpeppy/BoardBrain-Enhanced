import streamlit as st
import tempfile
import os
import pandas as pd
import processor
from dotenv import load_dotenv
import base64
import json
import streamlit.components.v1 as components
import altair as alt

# Load environment variables
load_dotenv()

# --- Page Config ---
st.set_page_config(
    page_title="BoardBrain",
    page_icon="🧠",
    layout="wide"
)

# --- Sidebar ---
st.sidebar.title("⚙️ Settings")

# Mock Mode Toggle
use_mock_mode = st.sidebar.checkbox("Enable Mock Mode", value=False, help="Use sample data to save API tokens.")

# Pre-fill keys from .env if available
default_assembly_key = os.getenv("ASSEMBLYAI_API_KEY", "")
default_openai_key = os.getenv("OPENAI_API_KEY", "")

# If Mock Mode is enabled, we hide the keys or disable them, but simpler to just ignore them in logic.
# However, for UI clarity:
if use_mock_mode:
    st.sidebar.warning("Running in Mock Mode. API keys will be ignored.")
    assemblyai_key = "dummy"
    openai_key = "dummy"
    # Show disabled inputs just for visual confirmation of what's happening
    st.sidebar.text_input("AssemblyAI API Key", value="dummy", disabled=True)
    st.sidebar.text_input("OpenAI API Key", value="dummy", disabled=True)
else:
    assemblyai_key = st.sidebar.text_input("AssemblyAI API Key", value=default_assembly_key, type="password")
    openai_key = st.sidebar.text_input("OpenAI API Key", value=default_openai_key, type="password")

st.sidebar.markdown("---")
st.sidebar.info(
    "**Note**: If keys are missing, the app will automatically fall back to 'Mock Mode'."
)

# --- Main Interface ---
st.title("🧠 BoardBrain")
st.markdown("### Turn HOA Board Videos into Actionable Data")

# Session State Initialization
if "step" not in st.session_state:
    st.session_state.step = "upload" # 'upload' or 'results'
if "processing_complete" not in st.session_state:
    st.session_state.processing_complete = False
if "intelligence_data" not in st.session_state:
    st.session_state.intelligence_data = None
if "formatted_transcript" not in st.session_state:
    st.session_state.formatted_transcript = ""
if "raw_transcript" not in st.session_state:
    st.session_state.raw_transcript = {}
if "audio_path" not in st.session_state:
    st.session_state.audio_path = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --- Step 1: Upload & Process ---
if st.session_state.step == "upload":

    st.markdown("#### Step 1: Upload Materials")

    col1, col2 = st.columns(2)

    with col1:
        st.info("Upload your board meeting video here.")
        uploaded_file = st.file_uploader("Upload Meeting Video", type=["mp4", "mov", "avi"])

    with col2:
        st.info("Upload or paste bylaws for Parliamentarian Mode.")
        bylaws_file = st.file_uploader("Upload Bylaws Document", type=["txt", "pdf", "docx"])
        bylaws_paste = st.text_area("Or Paste Bylaws Text Here", height=150)

    st.markdown("---")

    if uploaded_file is not None:
        if st.button("Process Meeting", type="primary", use_container_width=True):

            # Validation
            if not assemblyai_key:
                st.warning("No AssemblyAI Key provided. Using Mock Mode for Transcription.")
            if not openai_key:
                st.warning("No OpenAI Key provided. Using Mock Mode for Intelligence.")

            status_container = st.status("Processing Meeting...", expanded=True)

            try:
                # 1. Save File Temporarily
                status_container.write("📂 Saving uploaded file...")
                tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") # Or infer extension
                tfile.write(uploaded_file.read())
                video_path = tfile.name
                tfile.close()

                # 2. Extract Audio
                status_container.write("🔊 Extracting audio from video...")
                audio_path = processor.extract_audio(video_path)

                # 3. Transcribe
                status_container.write("📝 Transcribing audio with AssemblyAI...")
                transcript_obj = processor.transcribe_audio(audio_path, assemblyai_key)
                st.session_state.raw_transcript = transcript_obj

                # 4. Format
                status_container.write("📄 Formatting transcript...")
                formatted_text = processor.format_transcript(transcript_obj)
                st.session_state.formatted_transcript = formatted_text

                # 5. Extract Intelligence
                status_container.write("🧠 Extracting insights with GPT-4o...")

                # Prepare Bylaws Text
                bylaws_text = ""
                if bylaws_file:
                    bylaws_text += processor.read_file_content(bylaws_file, bylaws_file.name) + "\n"
                if bylaws_paste:
                    bylaws_text += bylaws_paste

                # Count Speakers
                speakers_count = 0
                if "utterances" in transcript_obj:
                    speakers = set(u.get("speaker") for u in transcript_obj["utterances"])
                    speakers_count = len(speakers)

                intelligence = processor.extract_intelligence(formatted_text, openai_key, bylaws_text=bylaws_text, speakers_count=speakers_count)
                st.session_state.intelligence_data = intelligence

                # Reset chat history on new process
                st.session_state.chat_history = []

                # Cleanup
                status_container.write("🧹 Cleaning up temporary files...")
                if os.path.exists(video_path):
                    os.remove(video_path)

                # Store audio path for playback - clean up previous if exists
                if st.session_state.audio_path and os.path.exists(st.session_state.audio_path) and st.session_state.audio_path != audio_path:
                    os.remove(st.session_state.audio_path)

                st.session_state.audio_path = audio_path
                st.session_state.processing_complete = True

                # TRANSITION TO RESULTS
                status_container.update(label="Processing Complete!", state="complete", expanded=False)
                st.session_state.step = "results"
                st.rerun()

            except Exception as e:
                status_container.update(label="Error Occurred", state="error")
                st.error(f"An error occurred during processing: {str(e)}")
                # Attempt cleanup even on error
                if 'video_path' in locals() and os.path.exists(video_path):
                    os.remove(video_path)
                if 'audio_path' in locals() and os.path.exists(audio_path):
                    os.remove(audio_path)
    else:
        st.warning("Please upload a video file to proceed.")

# --- Step 2: Display Results ---
elif st.session_state.step == "results" and st.session_state.processing_complete:

    # Header with Back Button
    col_head_1, col_head_2 = st.columns([4, 1])
    with col_head_1:
        st.success("Meeting Processed Successfully!")
    with col_head_2:
        if st.button("🔄 Start Over", type="secondary"):
            st.session_state.step = "upload"
            st.session_state.processing_complete = False
            st.session_state.intelligence_data = None
            st.rerun()

    st.markdown("---")

    data = st.session_state.intelligence_data

    # Export Section
    col_export_1, col_export_2 = st.columns([2, 1])
    with col_export_1:
        st.subheader("Results")
    with col_export_2:
        include_transcript_in_doc = st.checkbox("Include Transcript in Export")

        @st.cache_data
        def get_cached_document(data, transcript, include_transcript):
            """
            Wrapper to cache the document generation.
            Returns the bytes of the generated file.
            """
            buffer = processor.generate_word_document(data, transcript, include_transcript)
            return buffer.getvalue()

        # Generate the document (cached)
        doc_bytes = get_cached_document(
            data,
            st.session_state.formatted_transcript,
            include_transcript_in_doc
        )

        st.download_button(
            label="📄 Download Word Doc",
            data=doc_bytes,
            file_name=f"Meeting_Notes_{data.get('meeting_date', 'Unknown')}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

    tab1, tab2, tab3 = st.tabs(["📊 Insights", "📜 Full Transcript", "💬 Chat with Meeting"])

    with tab1:
        st.subheader("Executive Summary")
        st.info(data.get("summary", "No summary available."))

        col1, col2 = st.columns(2)
        with col1:
            st.caption(f"**Meeting Date**: {data.get('meeting_date', 'Unknown')}")

        st.subheader("🗣️ Speaking Time Distribution")
        speaking_times = processor.calculate_speaking_time(st.session_state.raw_transcript)
        if speaking_times:
            df_speaking = pd.DataFrame(list(speaking_times.items()), columns=['Speaker', 'Time (ms)'])
            df_speaking['Time (s)'] = df_speaking['Time (ms)'] / 1000

            base = alt.Chart(df_speaking).encode(
                theta=alt.Theta("Time (s)", stack=True)
            )
            pie = base.mark_arc(outerRadius=120).encode(
                color=alt.Color("Speaker"),
                order=alt.Order("Time (s)", sort="descending"),
                tooltip=["Speaker", alt.Tooltip("Time (s)", format=".1f")]
            )
            text = base.mark_text(radius=140).encode(
                text=alt.Text("Time (s)", format=".1f"),
                order=alt.Order("Time (s)", sort="descending"),
                color=alt.value("black")
            )
            st.altair_chart(pie + text, use_container_width=True)
        else:
            st.info("No speaking time data available.")

        st.subheader("📋 Motions")
        motions = data.get("motions", [])
        if motions:
            df_motions = pd.DataFrame(motions)
            st.dataframe(df_motions, use_container_width=True)
        else:
            st.write("No motions detected.")

        st.subheader("✅ Action Items")
        actions = data.get("action_items", [])
        if actions:
            df_actions = pd.DataFrame(actions)
            st.dataframe(df_actions, use_container_width=True)
        else:
            st.write("No action items detected.")

    with tab2:
        # Interactive Transcript
        if st.session_state.audio_path and os.path.exists(st.session_state.audio_path):

            # Read audio file as base64
            with open(st.session_state.audio_path, "rb") as f:
                audio_bytes = f.read()
            audio_base64 = base64.b64encode(audio_bytes).decode()
            audio_data_uri = f"data:audio/mp3;base64,{audio_base64}"

            # Prepare Transcript Data for JS
            transcript_data = st.session_state.raw_transcript.get("utterances", [])
            # Fallback if no utterances (e.g. no speaker labels)
            if not transcript_data and "text" in st.session_state.raw_transcript:
                # Create a single dummy utterance for the whole text
                transcript_data = [{"speaker": "Unknown", "text": st.session_state.raw_transcript["text"], "start": 0, "end": 9999999}]

            # Ensure 'words' exist for word-by-word highlighting
            for utt in transcript_data:
                if "words" not in utt:
                    # Create dummy words by splitting text
                    words = utt.get("text", "").split(" ")
                    utt["words"] = []
                    duration = utt.get("end", 0) - utt.get("start", 0)
                    if duration < 0: duration = 1000
                    word_duration = duration / max(len(words), 1)
                    current_time = utt.get("start", 0)

                    for w in words:
                        utt["words"].append({
                            "text": w,
                            "start": current_time,
                            "end": current_time + word_duration
                        })
                        current_time += word_duration

            transcript_json = json.dumps(transcript_data)

            # HTML/JS/CSS Component
            html_code = f"""
            <html>
            <head>
                <style>
                    body {{
                        font-family: sans-serif;
                        color: #31333F;
                        background-color: white;
                    }}
                    .audio-container {{
                        position: sticky;
                        top: 0;
                        background: white;
                        padding: 10px 0;
                        border-bottom: 1px solid #ddd;
                        z-index: 100;
                    }}
                    audio {{
                        width: 100%;
                    }}
                    .transcript-container {{
                        max-height: 600px;
                        overflow-y: auto;
                        padding: 20px 0;
                    }}
                    .utterance {{
                        padding: 10px;
                        border-radius: 5px;
                        margin-bottom: 10px;
                        transition: background-color 0.2s;
                    }}
                    .utterance:hover {{
                        background-color: #f0f2f6;
                    }}
                    .utterance.active {{
                        border-left: 4px solid #2e7af1;
                    }}
                    .speaker-badge {{
                        display: inline-block;
                        padding: 2px 6px;
                        border-radius: 4px;
                        font-weight: bold;
                        font-size: 0.8em;
                        margin-bottom: 4px;
                        color: white;
                        background-color: #555;
                    }}
                    .speaker-Takara {{ background-color: #ff4b4b; }}
                    .speaker-Jennifer {{ background-color: #2e7af1; }}
                    .speaker-Bill {{ background-color: #2bb02b; }}
                    .speaker-A {{ background-color: #ff4b4b; }}
                    .speaker-B {{ background-color: #2e7af1; }}
                    .speaker-C {{ background-color: #2bb02b; }}

                    .word {{
                        cursor: pointer;
                        padding: 1px 2px;
                        border-radius: 3px;
                        transition: background-color 0.1s;
                    }}
                    .word:hover {{
                        background-color: #e0e0e0;
                    }}
                    .word.active {{
                        background-color: #8da4ef;
                        color: white;
                    }}

                    @media (prefers-color-scheme: dark) {{
                        body {{
                            background-color: #0E1117;
                            color: #FAFAFA;
                        }}
                        .audio-container {{
                            background: #0E1117;
                            border-bottom: 1px solid #333;
                        }}
                        .utterance:hover {{
                            background-color: #262730;
                        }}
                        .word:hover {{
                            background-color: #333;
                        }}
                    }}
                </style>
            </head>
            <body>
                <div class="audio-container">
                    <audio id="player" controls>
                        <source src="{audio_data_uri}" type="audio/mp3">
                        Your browser does not support the audio element.
                    </audio>
                </div>
                <div class="transcript-container" id="transcript">
                    <!-- Content injected via JS -->
                </div>

                <script>
                    const transcriptData = {transcript_json};
                    const transcriptContainer = document.getElementById('transcript');
                    const player = document.getElementById('player');

                    // Render Transcript
                    transcriptData.forEach((utt, index) => {{
                        const div = document.createElement('div');
                        div.className = 'utterance';
                        div.id = 'utt-' + index;
                        div.dataset.start = utt.start; // ms
                        div.dataset.end = utt.end;     // ms

                        // Speaker Badge
                        const speakerBadge = document.createElement('span');
                        // Use first name for class color mapping
                        const firstName = utt.speaker.split(' ')[0];
                        speakerBadge.className = 'speaker-badge speaker-' + firstName;
                        speakerBadge.innerText = utt.speaker;
                        div.appendChild(speakerBadge);

                        // Line break
                        div.appendChild(document.createElement('br'));

                        // Words container (implicit in div)
                        if (utt.words) {{
                            utt.words.forEach((word, wIndex) => {{
                                const wordSpan = document.createElement('span');
                                wordSpan.className = 'word';
                                wordSpan.id = 'word-' + index + '-' + wIndex;
                                wordSpan.dataset.start = word.start;
                                wordSpan.dataset.end = word.end;
                                wordSpan.innerText = word.text + ' ';

                                // Click word to seek
                                wordSpan.onclick = (e) => {{
                                    e.stopPropagation(); // Prevent utterance click
                                    player.currentTime = word.start / 1000;
                                    player.play();
                                }};

                                div.appendChild(wordSpan);
                            }});
                        }} else {{
                             // Fallback if no words (should generally be handled by python logic)
                             const textSpan = document.createElement('span');
                             textSpan.innerText = utt.text;
                             div.appendChild(textSpan);
                        }}

                        transcriptContainer.appendChild(div);
                    }});

                    // Highlight active words
                    let currentActiveWordId = null;
                    let currentActiveUttIndex = -1;

                    player.ontimeupdate = () => {{
                        const timeMs = player.currentTime * 1000;

                        // 1. Find active Utterance (Optimization: check current first)
                        let activeUttIndex = -1;

                        // Check if still in current utterance
                        if (currentActiveUttIndex !== -1) {{
                            const utt = transcriptData[currentActiveUttIndex];
                            if (timeMs >= utt.start && timeMs <= utt.end) {{
                                activeUttIndex = currentActiveUttIndex;
                            }}
                        }}

                        // If not, search all (or search from current forward)
                        if (activeUttIndex === -1) {{
                            for (let i = 0; i < transcriptData.length; i++) {{
                                const utt = transcriptData[i];
                                if (timeMs >= utt.start && timeMs < utt.end) {{
                                    activeUttIndex = i;
                                    break;
                                }}
                            }}
                        }}

                        // 2. If inside an utterance, find the active word
                        if (activeUttIndex !== -1) {{
                            currentActiveUttIndex = activeUttIndex; // Update cache
                            const utt = transcriptData[activeUttIndex];

                            // Highlight utterance container
                             const uttDiv = document.getElementById('utt-' + activeUttIndex);
                             if (uttDiv && !uttDiv.classList.contains('active')) {{
                                 // clear old active utterances
                                 document.querySelectorAll('.utterance.active').forEach(el => el.classList.remove('active'));
                                 uttDiv.classList.add('active');
                             }}

                            if (utt.words) {{
                                for (let j = 0; j < utt.words.length; j++) {{
                                    const word = utt.words[j];
                                    if (timeMs >= word.start && timeMs < word.end) {{
                                        const wordId = 'word-' + activeUttIndex + '-' + j;

                                        if (currentActiveWordId !== wordId) {{
                                            // Remove previous
                                            if (currentActiveWordId) {{
                                                const prev = document.getElementById(currentActiveWordId);
                                                if (prev) prev.classList.remove('active');
                                            }}

                                            // Add new
                                            const next = document.getElementById(wordId);
                                            if (next) {{
                                                next.classList.add('active');
                                                // Ensure the parent utterance is visible
                                                const parentUtt = document.getElementById('utt-' + activeUttIndex);
                                                if (parentUtt) {{
                                                    // Simple check: is it far off screen?
                                                    // For now, just scroll parent if the index CHANGED
                                                    if (currentActiveWordId === null || !currentActiveWordId.startsWith('word-' + activeUttIndex)) {{
                                                         parentUtt.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                                                    }}
                                                }}
                                            }}
                                            currentActiveWordId = wordId;
                                        }}
                                        break;
                                    }}
                                }}
                            }}
                        }}
                    }};
                </script>
            </body>
            </html>
            """

            components.html(html_code, height=600, scrolling=True)

        else:
            st.info("Audio file not available for playback. Please process a video.")

    with tab3:
        st.subheader("Chat with your Meeting")

        # Display chat messages from history on app rerun
        for message in st.session_state.chat_history:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # React to user input
        if prompt := st.chat_input("Ask a question about the meeting..."):
            # Display user message in chat message container
            st.chat_message("user").markdown(prompt)
            # Add user message to chat history
            st.session_state.chat_history.append({"role": "user", "content": prompt})

            # Get response from processor
            with st.spinner("Thinking..."):
                response_text = processor.chat_with_meeting(
                    st.session_state.formatted_transcript,
                    st.session_state.chat_history,
                    prompt,
                    openai_key
                )

            # Display assistant response in chat message container
            with st.chat_message("assistant"):
                st.markdown(response_text)
            # Add assistant response to chat history
            st.session_state.chat_history.append({"role": "assistant", "content": response_text})
