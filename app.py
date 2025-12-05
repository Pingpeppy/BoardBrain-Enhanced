import streamlit as st
import tempfile
import os
import pandas as pd
import processor
import database
import base64
import json
import streamlit.components.v1 as components
import altair as alt

# --- Page Config ---
st.set_page_config(
    page_title="BoardBrain",
    page_icon="🧠",
    layout="wide"
)

# --- Sidebar Layout ---
chat_container = st.sidebar.container()
settings_container = st.sidebar.container()

# --- Sidebar Settings (Moved to Container) ---
with settings_container:
    st.sidebar.title("⚙️ Settings")

    # Mock Mode Toggle
    use_mock_mode = st.sidebar.checkbox("Enable Mock Mode", value=False, help="Use sample data to save API tokens.")

    # Pre-fill keys from st.secrets if available (fallback to manual entry)
    default_assembly_key = st.secrets.get("ASSEMBLYAI_API_KEY", "")
    default_openai_key = st.secrets.get("OPENAI_API_KEY", "")

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

        # Warning if keys are missing
        if not assemblyai_key or not openai_key:
            st.sidebar.warning("⚠️ API Keys are missing. Please configure secrets or enter them above.")

    st.sidebar.markdown("---")

    # Supabase Settings
    st.sidebar.subheader("Database")
    default_supabase_url = st.secrets.get("SUPABASE_URL", "")
    default_supabase_key = st.secrets.get("SUPABASE_KEY", "")

    if use_mock_mode:
        supabase_url = "dummy"
        supabase_key = "dummy"
        st.sidebar.text_input("Supabase URL", value="dummy", disabled=True)
        st.sidebar.text_input("Supabase Key", value="dummy", disabled=True)
    else:
        supabase_url = st.sidebar.text_input("Supabase URL", value=default_supabase_url, type="default", help="Your Supabase project URL")
        supabase_key = st.sidebar.text_input("Supabase Key", value=default_supabase_key, type="password", help="Your Supabase anon/service key")

        if not supabase_url or not supabase_key:
            st.sidebar.caption("Database not configured. Meetings will not be saved.")

    st.sidebar.markdown("---")
    st.sidebar.info(
        "**Note**: If keys are missing, the app will automatically fall back to 'Mock Mode'."
    )

# Initialize Supabase Manager
db = database.SupabaseManager(url=supabase_url, key=supabase_key)

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
if "bylaws_text" not in st.session_state:
    st.session_state.bylaws_text = ""
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "current_meeting_id" not in st.session_state:
    st.session_state.current_meeting_id = None
if "video_filename" not in st.session_state:
    st.session_state.video_filename = ""

# --- Step 1: Upload & Process ---
if st.session_state.step == "upload":

    # --- Previous Meetings Section ---
    if db.is_connected():
        previous_meetings = db.list_meetings(limit=10)
        if previous_meetings:
            st.markdown("#### Previous Meetings")
            st.caption("Load a previously processed meeting or upload a new one.")

            # Create a selectbox with meeting options
            meeting_options = ["-- Select a meeting --"] + [
                f"{m.get('video_filename', 'Unknown')} ({m.get('meeting_date', 'No date')}) - {m.get('created_at', '')[:10]}"
                for m in previous_meetings
            ]

            selected_meeting_idx = st.selectbox(
                "Load Previous Meeting",
                range(len(meeting_options)),
                format_func=lambda x: meeting_options[x],
                key="meeting_selector"
            )

            col_load, col_delete = st.columns([3, 1])

            with col_load:
                if selected_meeting_idx > 0 and st.button("Load Meeting", type="primary"):
                    meeting = previous_meetings[selected_meeting_idx - 1]
                    meeting_id = meeting.get("id")

                    with st.spinner("Loading meeting data..."):
                        full_data = db.load_full_meeting(meeting_id)

                        if full_data:
                            # Restore session state from database
                            st.session_state.current_meeting_id = meeting_id
                            st.session_state.video_filename = meeting.get("video_filename", "")

                            if full_data.get("transcript"):
                                # Apply speaker name mappings from speakers table to transcript
                                transcript = full_data["transcript"]
                                speakers_data = full_data.get("speakers", [])

                                if speakers_data and "utterances" in transcript:
                                    # Create mapping from original_label to assigned_name
                                    speaker_map = {
                                        s.get("original_label"): s.get("assigned_name")
                                        for s in speakers_data
                                        if s.get("original_label") and s.get("assigned_name")
                                    }

                                    # Apply mappings to utterances
                                    for utterance in transcript["utterances"]:
                                        old_label = utterance.get("speaker")
                                        if old_label in speaker_map:
                                            utterance["speaker"] = speaker_map[old_label]

                                st.session_state.raw_transcript = transcript
                                st.session_state.formatted_transcript = processor.format_transcript(transcript)

                            if full_data.get("intelligence"):
                                st.session_state.intelligence_data = full_data["intelligence"]

                            if full_data.get("chat_history"):
                                st.session_state.chat_history = full_data["chat_history"]
                            else:
                                st.session_state.chat_history = []

                            st.session_state.bylaws_text = full_data.get("bylaws_text", "")

                            # Note: audio_path won't be available for loaded meetings
                            st.session_state.audio_path = None

                            st.session_state.processing_complete = True
                            st.session_state.step = "results"
                            st.rerun()
                        else:
                            st.error("Failed to load meeting data.")

            with col_delete:
                if selected_meeting_idx > 0 and st.button("Delete", type="secondary"):
                    meeting = previous_meetings[selected_meeting_idx - 1]
                    meeting_id = meeting.get("id")
                    if db.delete_meeting(meeting_id):
                        st.success("Meeting deleted!")
                        st.rerun()
                    else:
                        st.error("Failed to delete meeting.")

            st.markdown("---")

    st.markdown("#### Upload New Meeting")

    col1, col2 = st.columns(2)

    with col1:
        st.info("Upload your board meeting video here.")
        uploaded_file = st.file_uploader("Upload Meeting Video", type=["mp4", "mov", "avi"])

    with col2:
        info_col, help_col = st.columns([0.9, 0.1])
        with info_col:
            st.info("Upload or paste bylaws for Parliamentarian Mode.")
        with help_col:
            with st.popover("ℹ️", help="What is Parliamentarian Mode?"):
                st.markdown(
                    """
                    **What is Parliamentarian Mode?**

                    Think of this as your digital meeting compliance assistant! It helps ensure your meeting follows standard procedures (like Robert's Rules of Order).

                    *   **Validates Motions**: It checks if motions were properly 'Seconded'. If not, it marks them as failed.
                    *   **Checks Quorum**: If you provide your bylaws, it compares the number of speakers to your requirements to warn you if there weren't enough people for an official vote.
                    """
                )

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
                if use_mock_mode:
                    status_container.write("🔊 (Mock) Using dummy audio...")
                    tfile_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
                    tfile_audio.write(b"ID3" + b"\x00"*10)
                    tfile_audio.close()
                    audio_path = tfile_audio.name
                else:
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

                # --- Store Original Speaker Labels (Before Auto-Suggest) ---
                original_speaker_labels = {}
                if "utterances" in transcript_obj:
                    # Create mapping of current speaker names
                    for utterance in transcript_obj["utterances"]:
                        speaker = utterance.get("speaker")
                        if speaker:
                            original_speaker_labels[speaker] = speaker
                # ---------------------------------------------------------

                # --- Auto-Suggest Speaker Names (New Step) ---
                suggestions = {}  # Initialize to avoid scope issues
                if "utterances" in transcript_obj:
                    status_container.write("🕵️ Identifying speakers...")
                    suggestions = processor.suggest_speaker_names(formatted_text, openai_key)

                    if suggestions:
                        # Auto-update transcript
                        for utterance in transcript_obj["utterances"]:
                            old_name = utterance["speaker"]
                            if old_name in suggestions:
                                utterance["speaker"] = suggestions[old_name]

                        # Re-format with new names
                        formatted_text = processor.format_transcript(transcript_obj)
                        st.session_state.formatted_transcript = formatted_text
                        st.session_state.raw_transcript = transcript_obj # Save updated raw

                        # Store for UI
                        st.session_state.speaker_suggestions = suggestions
                        status_container.write(f"✅ Auto-identified {len(suggestions)} speakers!")
                # ---------------------------------------------

                # 5. Extract Intelligence
                status_container.write("🧠 Extracting insights with GPT-4o...")

                # Prepare Bylaws Text
                bylaws_text = ""
                if bylaws_file:
                    bylaws_text += processor.read_file_content(bylaws_file, bylaws_file.name) + "\n"
                if bylaws_paste:
                    bylaws_text += bylaws_paste

                # Store bylaws text in session state for re-processing later
                st.session_state.bylaws_text = bylaws_text

                # Count Speakers
                speakers_count = 0
                if "utterances" in transcript_obj:
                    speakers = set(u.get("speaker") for u in transcript_obj["utterances"])
                    speakers_count = len(speakers)

                intelligence = processor.extract_intelligence(formatted_text, openai_key, bylaws_text=bylaws_text, speakers_count=speakers_count)
                st.session_state.intelligence_data = intelligence

                # Reset chat history on new process
                st.session_state.chat_history = []

                # Store video filename
                st.session_state.video_filename = uploaded_file.name

                # --- Save to Database ---
                if db.is_connected():
                    status_container.write("💾 Saving to database...")

                    # Calculate duration
                    duration_min = 0
                    if "utterances" in transcript_obj and transcript_obj["utterances"]:
                        last_end = transcript_obj["utterances"][-1].get("end", 0)
                        duration_min = round(last_end / 1000 / 60)

                    # Create meeting record
                    meeting_data = {
                        "video_filename": uploaded_file.name,
                        "meeting_date": intelligence.get("meeting_date"),
                        "duration_minutes": duration_min,
                        "speakers_count": speakers_count
                    }

                    meeting_id = db.save_meeting(meeting_data)

                    if meeting_id:
                        st.session_state.current_meeting_id = meeting_id

                        # Save transcript
                        db.save_transcript(meeting_id, transcript_obj)

                        # Save intelligence
                        db.save_intelligence(meeting_id, intelligence)

                        # Save bylaws if provided
                        if bylaws_text:
                            db.save_bylaws(meeting_id, bylaws_text)

                        # Save speaker info with original labels
                        speaking_times = processor.calculate_speaking_time(transcript_obj)
                        speakers_data = []

                        # Create reverse mapping: current_name -> original_label
                        current_to_original = {}
                        for original_label in original_speaker_labels.keys():
                            # Find the current name in utterances
                            for utterance in transcript_obj["utterances"]:
                                # Check if this utterance was originally from this speaker
                                current_name = utterance.get("speaker")
                                if original_label in suggestions and suggestions[original_label] == current_name:
                                    current_to_original[current_name] = original_label
                                    break
                                elif original_label not in suggestions and current_name == original_label:
                                    current_to_original[current_name] = original_label
                                    break

                        for speaker, time_ms in speaking_times.items():
                            original_label = current_to_original.get(speaker, speaker)
                            speakers_data.append({
                                "original_label": original_label,
                                "assigned_name": speaker,
                                "speaking_time_ms": time_ms
                            })
                        db.save_speakers(meeting_id, speakers_data)

                        status_container.write("✅ Meeting saved to database!")
                # --------------------------

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
            st.session_state.current_meeting_id = None
            st.session_state.video_filename = ""
            st.session_state.chat_history = []
            st.rerun()

    st.markdown("---")

    data = st.session_state.intelligence_data

    # --- Assistant Moved to Sidebar ---
    # Render into the chat container defined at the top
    with chat_container:
        st.subheader("💬 Assistant")
        st.markdown("Ask questions about your meeting.")

        # Container for chat messages
        chat_msg_container = st.container(height=500)

        # Display chat messages from history on app rerun
        with chat_msg_container:
            for message in st.session_state.chat_history:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

        # React to user input (Form used because st.chat_input cannot be in columns/sidebar easily with other layout needs)
        with st.form(key="chat_form", clear_on_submit=True):
            user_input = st.text_input("Ask a question...", key="chat_msg_input")
            submit_button = st.form_submit_button("Send")

        if submit_button and user_input:
            # Display user message in chat message container
            with chat_msg_container:
                st.chat_message("user").markdown(user_input)
            # Add user message to chat history
            st.session_state.chat_history.append({"role": "user", "content": user_input})

            # Save user message to database
            if db.is_connected() and st.session_state.current_meeting_id:
                db.save_chat_message(st.session_state.current_meeting_id, "user", user_input)

            # Get response from processor
            # Generate timestamped transcript on the fly for the chat context
            timestamped_transcript = processor.format_transcript_with_timestamps(st.session_state.raw_transcript)

            with st.spinner("Thinking..."):
                response_text = processor.chat_with_meeting(
                    timestamped_transcript,
                    st.session_state.chat_history,
                    user_input,
                    openai_key,
                    intelligence_data=st.session_state.intelligence_data
                )

            # Display assistant response in chat message container
            with chat_msg_container:
                with st.chat_message("assistant"):
                    st.markdown(response_text)
            # Add assistant response to chat history
            st.session_state.chat_history.append({"role": "assistant", "content": response_text})

            # Save assistant response to database
            if db.is_connected() and st.session_state.current_meeting_id:
                db.save_chat_message(st.session_state.current_meeting_id, "assistant", response_text)

        # Add separator between chat and settings
        st.markdown("---")

    # --- Main Content ---
    # TABS: Dashboard, Analytics, Transcript
    tab_dashboard, tab_analytics, tab_transcript = st.tabs(["📊 Dashboard", "📈 Analytics", "📜 Full Transcript"])

    # --- TAB 1: DASHBOARD ---
    with tab_dashboard:
        # Top Metrics
        m_col1, m_col2, m_col3 = st.columns(3)
        with m_col1:
            st.metric("Meeting Date", data.get("meeting_date", "Unknown"))
        with m_col2:
            # Calculate duration from transcript last utterance end
            duration_min = 0
            if "utterances" in st.session_state.raw_transcript and st.session_state.raw_transcript["utterances"]:
                    last_end = st.session_state.raw_transcript["utterances"][-1].get("end", 0)
                    duration_min = round(last_end / 1000 / 60)
            st.metric("Duration", f"{duration_min} mins")

        # Extract speakers count
        speakers_list = []
        if "utterances" in st.session_state.raw_transcript:
            speakers_set = set()
            for u in st.session_state.raw_transcript["utterances"]:
                if u.get("speaker"):
                    speakers_set.add(u["speaker"])
            speakers_list = sorted(list(speakers_set))

        with m_col3:
            st.metric("Attendees", len(speakers_list))

        st.markdown("---")

        # Executive Summary
        st.subheader("Executive Summary")
        st.info(data.get("summary", "No summary available."))

        col_motions, col_actions = st.columns(2)

        with col_motions:
            st.subheader("📋 Motions")
            motions = data.get("motions", [])
            if motions:
                df_motions = pd.DataFrame(motions)
                st.dataframe(df_motions, use_container_width=True, hide_index=True)
            else:
                st.write("No motions detected.")

        with col_actions:
            st.subheader("✅ Action Items")
            actions = data.get("action_items", [])
            if actions:
                df_actions = pd.DataFrame(actions)
                st.dataframe(df_actions, use_container_width=True, hide_index=True)
            else:
                st.write("No action items detected.")

        st.markdown("---")
        # Export Section (Moved here or keep at top? Kept at top of Dashboard for visibility)
        st.subheader("📄 Export Reports")
        include_transcript_in_doc = st.checkbox("Include Transcript in Export")

        @st.cache_data
        def get_cached_document(data, transcript, include_transcript):
            """
            Wrapper to cache the document generation.
            Returns the bytes of the generated file.
            """
            buffer = processor.generate_word_document(data, transcript, include_transcript)
            return buffer.getvalue()

        doc_bytes = get_cached_document(
            data,
            st.session_state.formatted_transcript,
            include_transcript_in_doc
        )

        st.download_button(
            label="Download Word Document",
            data=doc_bytes,
            file_name=f"Meeting_Notes_{data.get('meeting_date', 'Unknown')}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            type="primary"
        )


    # --- TAB 2: ANALYTICS ---
    with tab_analytics:
        st.subheader("Detailed Insights")

        # 1. Speaking Time (Existing)
        st.markdown("##### 🗣️ Speaking Time Distribution")
        speaking_times = processor.calculate_speaking_time(st.session_state.raw_transcript)
        if speaking_times:
            df_speaking = pd.DataFrame(list(speaking_times.items()), columns=['Speaker', 'Time (ms)'])
            df_speaking['Time (s)'] = df_speaking['Time (ms)'] / 1000

            base = alt.Chart(df_speaking).encode(
                theta=alt.Theta("Time (s)", stack=True)
            )
            pie = base.mark_arc(outerRadius=100).encode(
                color=alt.Color("Speaker"),
                order=alt.Order("Time (s)", sort="descending"),
                tooltip=["Speaker", alt.Tooltip("Time (s)", format=".1f")]
            )
            text = base.mark_text(radius=120).encode(
                text=alt.Text("Time (s)", format=".1f"),
                order=alt.Order("Time (s)", sort="descending"),
                color=alt.value("white") # Adjusted for dark mode
            )
            st.altair_chart(pie + text, use_container_width=True)
        else:
            st.info("No speaking time data available.")

        col_an_1, col_an_2 = st.columns(2)

        # 2. Topic Trends (New)
        with col_an_1:
            st.markdown("##### 📈 Topic Trends")
            topics_data = data.get("topic_trends", [])
            if topics_data:
                df_topics = pd.DataFrame(topics_data)
                chart_topics = alt.Chart(df_topics).mark_bar().encode(
                    x=alt.X('count', title='Mention Frequency'),
                    y=alt.Y('topic', sort='-x', title='Topic'),
                    color=alt.value("#0068c9"),
                    tooltip=['topic', 'count']
                )
                st.altair_chart(chart_topics, use_container_width=True)
            else:
                st.caption("No topic data available.")

        # 3. Sentiment Analysis (New)
        with col_an_2:
            st.markdown("##### 😊 Speaker Sentiment")
            sentiment_data = data.get("sentiment_analysis", {})
            per_speaker = sentiment_data.get("per_speaker", [])

            if per_speaker:
                df_sentiment = pd.DataFrame(per_speaker)
                # Map sentiment text to color/value manually for visualization if needed,
                # but a simple table or categorical chart works.
                # Let's try a heatmap-style grid or just a colored text list.

                st.dataframe(
                    df_sentiment,
                    column_config={
                        "sentiment": st.column_config.TextColumn("Sentiment")
                    },
                    use_container_width=True,
                    hide_index=True
                )
                st.caption(f"**Overall Meeting Sentiment:** {sentiment_data.get('overall', 'Unknown')}")
            else:
                st.caption("No sentiment data available.")


    # --- TAB 3: TRANSCRIPT ---
    with tab_transcript:

        # Search Bar
        search_query = st.text_input("🔍 Search Transcript", "")

        # --- Edit Speaker Names ---
        if "utterances" in st.session_state.raw_transcript and st.session_state.raw_transcript["utterances"]:
            with st.expander("✏️ Edit Speaker Names"):
                st.write("Rename speakers below. This will update the transcript and re-analyze the meeting intelligence.")

                # Get unique speakers
                unique_speakers = sorted(list(set(u["speaker"] for u in st.session_state.raw_transcript["utterances"])))

                # Auto-Suggest Button
                if st.button("✨ Auto-Suggest Names", type="primary", help="Analyze transcript to infer speaker names"):
                    with st.spinner("Analyzing transcript for names..."):
                        suggestions = processor.suggest_speaker_names(st.session_state.formatted_transcript, openai_key)

                        if suggestions:
                            st.success(f"Found {len(suggestions)} potential names!")
                            # Store suggestions in session state to pre-fill the form
                            st.session_state.speaker_suggestions = suggestions
                        else:
                            st.warning("No names could be inferred from the context.")
                            st.session_state.speaker_suggestions = {}

                # Ensure suggestions exist in session state
                if "speaker_suggestions" not in st.session_state:
                    st.session_state.speaker_suggestions = {}

                with st.form("speaker_rename_form"):
                    new_names = {}
                    cols = st.columns(3)
                    for i, speaker in enumerate(unique_speakers):
                        # Default value: Check suggestions first, then fall back to current name
                        suggested_name = st.session_state.speaker_suggestions.get(speaker, speaker)

                        with cols[i % 3]:
                            new_names[speaker] = st.text_input(
                                f"Rename '{speaker}'",
                                value=suggested_name,
                                help=f"Suggested: {suggested_name}" if speaker in st.session_state.speaker_suggestions else None
                            )

                    if st.form_submit_button("Save Changes & Reprocess"):
                        # Check if any changes were made
                        changes_made = any(new_names[s] != s for s in unique_speakers)

                        if changes_made:
                            status_container = st.status("Updating Speakers...", expanded=True)
                            try:
                                # 1. Update Utterances
                                status_container.write("🔄 Updating transcript data...")
                                for utterance in st.session_state.raw_transcript["utterances"]:
                                    old_name = utterance["speaker"]
                                    if old_name in new_names:
                                        utterance["speaker"] = new_names[old_name]

                                # 2. Re-format Transcript
                                status_container.write("📄 Re-formatting transcript...")
                                formatted_text = processor.format_transcript(st.session_state.raw_transcript)
                                st.session_state.formatted_transcript = formatted_text

                                # 3. Re-extract Intelligence
                                status_container.write("🧠 Re-analyzing meeting intelligence...")
                                # Recalculate speaker count
                                speakers_count = len(set(new_names.values()))

                                intelligence = processor.extract_intelligence(
                                    formatted_text,
                                    openai_key,
                                    bylaws_text=st.session_state.bylaws_text,
                                    speakers_count=speakers_count
                                )
                                st.session_state.intelligence_data = intelligence

                                # Clear suggestions after successful save
                                st.session_state.speaker_suggestions = {}

                                # 4. Update database if connected
                                if db.is_connected() and st.session_state.current_meeting_id:
                                    status_container.write("💾 Saving updates to database...")
                                    meeting_id = st.session_state.current_meeting_id

                                    # Update transcript
                                    db.update_transcript(meeting_id, st.session_state.raw_transcript)

                                    # Update intelligence
                                    db.update_intelligence(meeting_id, intelligence)

                                    # Update speakers
                                    speaking_times = processor.calculate_speaking_time(st.session_state.raw_transcript)
                                    speakers_data = []
                                    for speaker, time_ms in speaking_times.items():
                                        # Find original label if possible
                                        original_label = speaker
                                        for old, new in new_names.items():
                                            if new == speaker:
                                                original_label = old
                                                break
                                        speakers_data.append({
                                            "original_label": original_label,
                                            "assigned_name": speaker,
                                            "speaking_time_ms": time_ms
                                        })
                                    db.save_speakers(meeting_id, speakers_data)

                                status_container.update(label="Update Complete!", state="complete", expanded=False)
                                st.rerun()

                            except Exception as e:
                                status_container.update(label="Error Occurred", state="error")
                                st.error(f"An error occurred during update: {str(e)}")
                        else:
                            st.info("No changes detected.")

        # Interactive Transcript
        # Check if we have audio file for playback
        audio_available = st.session_state.audio_path and os.path.exists(st.session_state.audio_path)

        if audio_available:
            # Read audio file as base64
            with open(st.session_state.audio_path, "rb") as f:
                audio_bytes = f.read()
            audio_base64 = base64.b64encode(audio_bytes).decode()
            audio_data_uri = f"data:audio/mp3;base64,{audio_base64}"
        else:
            audio_data_uri = ""
            if st.session_state.raw_transcript:
                st.info("💡 Audio file not available. Showing transcript without audio playback.")

        # Always show transcript if we have it
        if st.session_state.raw_transcript:
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

            # Filter transcript data if search query exists
            if search_query:
                # Simple text match filtering for display logic in JS?
                # Actually, for the JS component we probably want the whole audio sync.
                # So we'll highlight matches or filter purely in Python for a static view.
                # Given the request for "Visuals", let's keep the interactive player intact
                # but maybe add a "Search Results" text block below if searching.
                pass

            transcript_json = json.dumps(transcript_data)

            # HTML/JS/CSS Component
            html_code = f"""
            <html>
            <head>
                <style>
                    body {{
                        font-family: sans-serif;
                        color: #fafafa;
                        background-color: #0e1117;
                    }}
                    .audio-container {{
                        position: sticky;
                        top: 0;
                        background: #0e1117;
                        padding: 10px 0;
                        border-bottom: 1px solid #333;
                        z-index: 100;
                        {'display: none;' if not audio_available else ''}
                    }}
                    audio {{
                        width: 100%;
                        filter: invert(1); /* Simple dark mode tweak for audio player */
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
                        border: 1px solid transparent;
                    }}
                    .utterance:hover {{
                        background-color: #262730;
                        border: 1px solid #444;
                    }}
                    .utterance.active {{
                        border-left: 4px solid #0068c9;
                        background-color: #1c1e26;
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
                    .speaker-Jennifer {{ background-color: #0068c9; }}
                    .speaker-Bill {{ background-color: #2bb02b; }}
                    .speaker-A {{ background-color: #ff4b4b; }}
                    .speaker-B {{ background-color: #0068c9; }}
                    .speaker-C {{ background-color: #2bb02b; }}

                    .word {{
                        cursor: pointer;
                        padding: 1px 2px;
                        border-radius: 3px;
                        transition: background-color 0.1s;
                    }}
                    .word:hover {{
                        background-color: #444;
                    }}
                    .word.active {{
                        background-color: #0068c9;
                        color: white;
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
                    const audioAvailable = {'true' if audio_available else 'false'};

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

                                // Click word to seek (only if audio available)
                                if (audioAvailable) {{
                                    wordSpan.onclick = (e) => {{
                                        e.stopPropagation(); // Prevent utterance click
                                        player.currentTime = word.start / 1000;
                                        player.play();
                                    }};
                                }}

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

                    // Highlight active words (only if audio available)
                    let currentActiveWordId = null;
                    let currentActiveUttIndex = -1;

                    if (audioAvailable) {{
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
                    }}
                </script>
            </body>
            </html>
            """

            components.html(html_code, height=600, scrolling=True)

        else:
            st.info("No transcript available. Please process a video first.")
