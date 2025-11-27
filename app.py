import streamlit as st
import tempfile
import os
import pandas as pd
import processor

# --- Page Config ---
st.set_page_config(
    page_title="BoardBrain",
    page_icon="🧠",
    layout="wide"
)

# --- Sidebar ---
st.sidebar.title("⚙️ Settings")
assemblyai_key = st.sidebar.text_input("AssemblyAI API Key", type="password", help="Leave blank or type 'dummy' to use Mock Mode.")
openai_key = st.sidebar.text_input("OpenAI API Key", type="password", help="Leave blank or type 'dummy' to use Mock Mode.")

st.sidebar.markdown("---")
st.sidebar.info(
    "**Note**: If keys are missing, the app will run in 'Mock Mode' with sample data."
)

# --- Main Interface ---
st.title("🧠 BoardBrain")
st.markdown("### Turn HOA Board Videos into Actionable Data")

# Session State Initialization
if "processing_complete" not in st.session_state:
    st.session_state.processing_complete = False
if "intelligence_data" not in st.session_state:
    st.session_state.intelligence_data = None
if "formatted_transcript" not in st.session_state:
    st.session_state.formatted_transcript = ""

# File Uploader
uploaded_file = st.file_uploader("Upload Board Meeting Video", type=["mp4", "mov", "avi"])

if uploaded_file is not None:
    # --- Process Button ---
    if st.button("Process Meeting", type="primary"):

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

            # 4. Format
            status_container.write("📄 Formatting transcript...")
            formatted_text = processor.format_transcript(transcript_obj)
            st.session_state.formatted_transcript = formatted_text

            # 5. Extract Intelligence
            status_container.write("🧠 Extracting insights with GPT-4o...")
            intelligence = processor.extract_intelligence(formatted_text, openai_key)
            st.session_state.intelligence_data = intelligence

            # Cleanup
            status_container.write("🧹 Cleaning up temporary files...")
            os.remove(video_path)
            os.remove(audio_path)

            status_container.update(label="Processing Complete!", state="complete", expanded=False)
            st.session_state.processing_complete = True

        except Exception as e:
            status_container.update(label="Error Occurred", state="error")
            st.error(f"An error occurred during processing: {str(e)}")
            # Attempt cleanup even on error
            if 'video_path' in locals() and os.path.exists(video_path):
                os.remove(video_path)
            if 'audio_path' in locals() and os.path.exists(audio_path):
                os.remove(audio_path)

# --- Display Results ---

if st.session_state.processing_complete and st.session_state.intelligence_data:
    st.markdown("---")

    data = st.session_state.intelligence_data

    tab1, tab2 = st.tabs(["📊 Insights", "📜 Full Transcript"])

    with tab1:
        st.subheader("Executive Summary")
        st.info(data.get("summary", "No summary available."))

        col1, col2 = st.columns(2)
        with col1:
            st.caption(f"**Meeting Date**: {data.get('meeting_date', 'Unknown')}")

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
        st.text_area("Transcript", value=st.session_state.formatted_transcript, height=600)
