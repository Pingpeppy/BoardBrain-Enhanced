"""
Supabase database integration for BoardBrain.
Handles all database operations for meeting persistence.
"""

import json
import os
import tempfile
from datetime import datetime
from typing import Optional, Any
import streamlit as st

# Try to import supabase, handle gracefully if not installed
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    Client = None


def _parse_jsonb(value: Any, default: Any = None) -> Any:
    """
    Safely parse JSONB data from Supabase.

    Supabase Python client auto-deserializes JSONB columns into Python objects,
    so we need to handle both cases:
    - Already a Python object (list/dict) -> return as-is
    - JSON string -> parse it
    - None/empty -> return default
    """
    if value is None:
        return default if default is not None else None
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return default if default is not None else None
    return default if default is not None else None


class SupabaseManager:
    """
    Manages all Supabase database operations for BoardBrain.
    Supports both real Supabase connections and mock mode for testing.
    """

    def __init__(self, url: Optional[str] = None, key: Optional[str] = None):
        """
        Initialize the Supabase client.

        Args:
            url: Supabase project URL
            key: Supabase API key (anon or service role)
        """
        self.client: Optional[Client] = None
        self.mock_mode = False

        # Check if Supabase is available
        if not SUPABASE_AVAILABLE:
            self.mock_mode = True
            return

        # Check for mock mode
        if not url or not key or url.strip().lower() == "dummy" or key.strip().lower() == "dummy":
            self.mock_mode = True
            return

        try:
            self.client = create_client(url, key)
        except Exception as e:
            st.warning(f"Failed to connect to Supabase: {str(e)}. Running in mock mode.")
            self.mock_mode = True

    def is_connected(self) -> bool:
        """Check if we have a valid Supabase connection."""
        return self.client is not None and not self.mock_mode

    # ==================== MEETING OPERATIONS ====================

    def save_meeting(self, meeting_data: dict) -> Optional[str]:
        """
        Save a new meeting record to the database.

        Args:
            meeting_data: Dictionary containing:
                - video_filename: Original video filename
                - meeting_date: Extracted meeting date (YYYY-MM-DD or None)
                - duration_minutes: Meeting duration
                - speakers_count: Number of speakers detected

        Returns:
            meeting_id (UUID string) if successful, None otherwise
        """
        if self.mock_mode:
            # Return a mock ID
            import uuid
            return str(uuid.uuid4())

        try:
            record = {
                "video_filename": meeting_data.get("video_filename", "Unknown"),
                "meeting_date": meeting_data.get("meeting_date"),
                "duration_minutes": meeting_data.get("duration_minutes", 0),
                "speakers_count": meeting_data.get("speakers_count", 0),
                "created_at": datetime.utcnow().isoformat()
            }

            result = self.client.table("meetings").insert(record).execute()

            if result.data and len(result.data) > 0:
                return result.data[0].get("id")
            return None

        except Exception as e:
            st.error(f"Error saving meeting: {str(e)}")
            return None

    def update_meeting(self, meeting_id: str, updates: dict) -> bool:
        """
        Update an existing meeting record.

        Args:
            meeting_id: UUID of the meeting to update
            updates: Dictionary of fields to update

        Returns:
            True if successful, False otherwise
        """
        if self.mock_mode:
            return True

        try:
            self.client.table("meetings").update(updates).eq("id", meeting_id).execute()
            return True
        except Exception as e:
            st.error(f"Error updating meeting: {str(e)}")
            return False

    def get_meeting(self, meeting_id: str) -> Optional[dict]:
        """
        Retrieve a meeting by ID.

        Args:
            meeting_id: UUID of the meeting

        Returns:
            Meeting record dictionary or None
        """
        if self.mock_mode:
            return None

        try:
            result = self.client.table("meetings").select("*").eq("id", meeting_id).execute()
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
        except Exception as e:
            st.error(f"Error retrieving meeting: {str(e)}")
            return None

    def list_meetings(self, limit: int = 50) -> list:
        """
        List all meetings, ordered by creation date (newest first).

        Args:
            limit: Maximum number of meetings to return

        Returns:
            List of meeting records
        """
        if self.mock_mode:
            return []

        try:
            result = self.client.table("meetings").select("*").order("created_at", desc=True).limit(limit).execute()
            return result.data or []
        except Exception as e:
            st.error(f"Error listing meetings: {str(e)}")
            return []

    def delete_meeting(self, meeting_id: str) -> bool:
        """
        Delete a meeting and all associated data.

        Args:
            meeting_id: UUID of the meeting to delete

        Returns:
            True if successful, False otherwise
        """
        if self.mock_mode:
            return True

        try:
            # Delete audio file from storage first
            self.delete_audio(meeting_id)

            # Delete related records first (cascading delete may handle this)
            self.client.table("chat_messages").delete().eq("meeting_id", meeting_id).execute()
            self.client.table("speakers").delete().eq("meeting_id", meeting_id).execute()
            self.client.table("intelligence").delete().eq("meeting_id", meeting_id).execute()
            self.client.table("transcripts").delete().eq("meeting_id", meeting_id).execute()
            self.client.table("meetings").delete().eq("id", meeting_id).execute()
            return True
        except Exception as e:
            st.error(f"Error deleting meeting: {str(e)}")
            return False

    # ==================== TRANSCRIPT OPERATIONS ====================

    def save_transcript(self, meeting_id: str, transcript_data: dict) -> bool:
        """
        Save transcript data for a meeting.

        Args:
            meeting_id: UUID of the associated meeting
            transcript_data: Raw transcript object from AssemblyAI

        Returns:
            True if successful, False otherwise
        """
        if self.mock_mode:
            return True

        try:
            record = {
                "meeting_id": meeting_id,
                "raw_text": transcript_data.get("text", ""),
                "utterances": json.dumps(transcript_data.get("utterances", [])),
                "created_at": datetime.utcnow().isoformat()
            }

            self.client.table("transcripts").insert(record).execute()
            return True

        except Exception as e:
            st.error(f"Error saving transcript: {str(e)}")
            return False

    def get_transcript(self, meeting_id: str) -> Optional[dict]:
        """
        Retrieve transcript data for a meeting.

        Args:
            meeting_id: UUID of the meeting

        Returns:
            Transcript object with utterances or None
        """
        if self.mock_mode:
            return None

        try:
            result = self.client.table("transcripts").select("*").eq("meeting_id", meeting_id).execute()

            if result.data and len(result.data) > 0:
                record = result.data[0]
                # Reconstruct the transcript object format
                # Note: JSONB columns are auto-deserialized by Supabase client
                return {
                    "text": record.get("raw_text", ""),
                    "utterances": _parse_jsonb(record.get("utterances"), [])
                }
            return None

        except Exception as e:
            st.error(f"Error retrieving transcript: {str(e)}")
            return None

    def update_transcript(self, meeting_id: str, transcript_data: dict) -> bool:
        """
        Update transcript data (e.g., after speaker renaming).

        Args:
            meeting_id: UUID of the meeting
            transcript_data: Updated transcript object

        Returns:
            True if successful, False otherwise
        """
        if self.mock_mode:
            return True

        try:
            updates = {
                "raw_text": transcript_data.get("text", ""),
                "utterances": json.dumps(transcript_data.get("utterances", [])),
                "updated_at": datetime.utcnow().isoformat()
            }

            self.client.table("transcripts").update(updates).eq("meeting_id", meeting_id).execute()
            return True

        except Exception as e:
            st.error(f"Error updating transcript: {str(e)}")
            return False

    # ==================== INTELLIGENCE OPERATIONS ====================

    def save_intelligence(self, meeting_id: str, intelligence_data: dict) -> bool:
        """
        Save extracted intelligence data for a meeting.

        Args:
            meeting_id: UUID of the meeting
            intelligence_data: Dictionary with motions, action_items, summary, etc.

        Returns:
            True if successful, False otherwise
        """
        if self.mock_mode:
            return True

        try:
            record = {
                "meeting_id": meeting_id,
                "meeting_date": intelligence_data.get("meeting_date"),
                "summary": intelligence_data.get("summary", ""),
                "motions": json.dumps(intelligence_data.get("motions", [])),
                "action_items": json.dumps(intelligence_data.get("action_items", [])),
                "sentiment_analysis": json.dumps(intelligence_data.get("sentiment_analysis", {})),
                "topic_trends": json.dumps(intelligence_data.get("topic_trends", [])),
                "financial_impact": json.dumps(intelligence_data.get("financial_impact", [])),
                "created_at": datetime.utcnow().isoformat()
            }

            self.client.table("intelligence").insert(record).execute()
            return True

        except Exception as e:
            st.error(f"Error saving intelligence: {str(e)}")
            return False

    def get_intelligence(self, meeting_id: str) -> Optional[dict]:
        """
        Retrieve intelligence data for a meeting.

        Args:
            meeting_id: UUID of the meeting

        Returns:
            Intelligence data dictionary or None
        """
        if self.mock_mode:
            return None

        try:
            result = self.client.table("intelligence").select("*").eq("meeting_id", meeting_id).execute()

            if result.data and len(result.data) > 0:
                record = result.data[0]
                # Reconstruct the intelligence object format
                # Note: JSONB columns are auto-deserialized by Supabase client
                return {
                    "meeting_date": record.get("meeting_date"),
                    "summary": record.get("summary", ""),
                    "motions": _parse_jsonb(record.get("motions"), []),
                    "action_items": _parse_jsonb(record.get("action_items"), []),
                    "sentiment_analysis": _parse_jsonb(record.get("sentiment_analysis"), {}),
                    "topic_trends": _parse_jsonb(record.get("topic_trends"), []),
                    "financial_impact": _parse_jsonb(record.get("financial_impact"), [])
                }
            return None

        except Exception as e:
            st.error(f"Error retrieving intelligence: {str(e)}")
            return None

    def update_intelligence(self, meeting_id: str, intelligence_data: dict) -> bool:
        """
        Update intelligence data (e.g., after reprocessing).

        Args:
            meeting_id: UUID of the meeting
            intelligence_data: Updated intelligence dictionary

        Returns:
            True if successful, False otherwise
        """
        if self.mock_mode:
            return True

        try:
            updates = {
                "meeting_date": intelligence_data.get("meeting_date"),
                "summary": intelligence_data.get("summary", ""),
                "motions": json.dumps(intelligence_data.get("motions", [])),
                "action_items": json.dumps(intelligence_data.get("action_items", [])),
                "sentiment_analysis": json.dumps(intelligence_data.get("sentiment_analysis", {})),
                "topic_trends": json.dumps(intelligence_data.get("topic_trends", [])),
                "financial_impact": json.dumps(intelligence_data.get("financial_impact", [])),
                "updated_at": datetime.utcnow().isoformat()
            }

            self.client.table("intelligence").update(updates).eq("meeting_id", meeting_id).execute()
            return True

        except Exception as e:
            st.error(f"Error updating intelligence: {str(e)}")
            return False

    # ==================== SPEAKER OPERATIONS ====================

    def save_speakers(self, meeting_id: str, speakers: list) -> bool:
        """
        Save speaker information for a meeting.

        Args:
            meeting_id: UUID of the meeting
            speakers: List of speaker dictionaries with:
                - original_label: Original speaker label (e.g., "Speaker A")
                - assigned_name: User-assigned name (e.g., "John Doe")
                - speaking_time_ms: Total speaking time in milliseconds

        Returns:
            True if successful, False otherwise
        """
        if self.mock_mode:
            return True

        try:
            # Delete existing speakers for this meeting first
            self.client.table("speakers").delete().eq("meeting_id", meeting_id).execute()

            # Insert new speaker records
            records = []
            for speaker in speakers:
                records.append({
                    "meeting_id": meeting_id,
                    "original_label": speaker.get("original_label", ""),
                    "assigned_name": speaker.get("assigned_name", ""),
                    "speaking_time_ms": speaker.get("speaking_time_ms", 0),
                    "created_at": datetime.utcnow().isoformat()
                })

            if records:
                self.client.table("speakers").insert(records).execute()

            return True

        except Exception as e:
            st.error(f"Error saving speakers: {str(e)}")
            return False

    def get_speakers(self, meeting_id: str) -> list:
        """
        Retrieve speaker information for a meeting.

        Args:
            meeting_id: UUID of the meeting

        Returns:
            List of speaker dictionaries
        """
        if self.mock_mode:
            return []

        try:
            result = self.client.table("speakers").select("*").eq("meeting_id", meeting_id).execute()
            return result.data or []
        except Exception as e:
            st.error(f"Error retrieving speakers: {str(e)}")
            return []

    # ==================== CHAT HISTORY OPERATIONS ====================

    def save_chat_message(self, meeting_id: str, role: str, content: str) -> bool:
        """
        Save a single chat message.

        Args:
            meeting_id: UUID of the meeting
            role: 'user' or 'assistant'
            content: Message content

        Returns:
            True if successful, False otherwise
        """
        if self.mock_mode:
            return True

        try:
            record = {
                "meeting_id": meeting_id,
                "role": role,
                "content": content,
                "created_at": datetime.utcnow().isoformat()
            }

            self.client.table("chat_messages").insert(record).execute()
            return True

        except Exception as e:
            st.error(f"Error saving chat message: {str(e)}")
            return False

    def get_chat_history(self, meeting_id: str) -> list:
        """
        Retrieve chat history for a meeting.

        Args:
            meeting_id: UUID of the meeting

        Returns:
            List of chat message dictionaries with 'role' and 'content'
        """
        if self.mock_mode:
            return []

        try:
            result = self.client.table("chat_messages").select("role, content").eq("meeting_id", meeting_id).order("created_at").execute()
            return result.data or []
        except Exception as e:
            st.error(f"Error retrieving chat history: {str(e)}")
            return []

    def clear_chat_history(self, meeting_id: str) -> bool:
        """
        Clear all chat messages for a meeting.

        Args:
            meeting_id: UUID of the meeting

        Returns:
            True if successful, False otherwise
        """
        if self.mock_mode:
            return True

        try:
            self.client.table("chat_messages").delete().eq("meeting_id", meeting_id).execute()
            return True
        except Exception as e:
            st.error(f"Error clearing chat history: {str(e)}")
            return False

    # ==================== BYLAWS OPERATIONS ====================

    def save_bylaws(self, meeting_id: str, bylaws_text: str) -> bool:
        """
        Save bylaws text associated with a meeting.

        Args:
            meeting_id: UUID of the meeting
            bylaws_text: The bylaws content

        Returns:
            True if successful, False otherwise
        """
        if self.mock_mode:
            return True

        try:
            # Update the meeting record with bylaws
            self.client.table("meetings").update({
                "bylaws_text": bylaws_text
            }).eq("id", meeting_id).execute()
            return True
        except Exception as e:
            st.error(f"Error saving bylaws: {str(e)}")
            return False

    def get_bylaws(self, meeting_id: str) -> str:
        """
        Retrieve bylaws text for a meeting.

        Args:
            meeting_id: UUID of the meeting

        Returns:
            Bylaws text or empty string
        """
        if self.mock_mode:
            return ""

        try:
            result = self.client.table("meetings").select("bylaws_text").eq("id", meeting_id).execute()
            if result.data and len(result.data) > 0:
                return result.data[0].get("bylaws_text", "") or ""
            return ""
        except Exception as e:
            st.error(f"Error retrieving bylaws: {str(e)}")
            return ""

    # ==================== AUDIO STORAGE OPERATIONS ====================

    def upload_audio(self, meeting_id: str, audio_file_path: str) -> bool:
        """
        Upload audio file to Supabase Storage.

        Args:
            meeting_id: UUID of the meeting
            audio_file_path: Local path to the audio file

        Returns:
            True if successful, False otherwise
        """
        if self.mock_mode:
            return True

        if not os.path.exists(audio_file_path):
            st.error(f"Audio file not found: {audio_file_path}")
            return False

        try:
            # Read the audio file
            with open(audio_file_path, "rb") as f:
                audio_data = f.read()

            # Upload to Supabase Storage bucket 'meeting-audio'
            # Filename format: {meeting_id}.mp3
            file_name = f"{meeting_id}.mp3"

            self.client.storage.from_("meeting-audio").upload(
                file_name,
                audio_data,
                file_options={"content-type": "audio/mpeg"}
            )

            # Update meeting record with audio_stored flag
            self.client.table("meetings").update({
                "audio_stored": True
            }).eq("id", meeting_id).execute()

            return True

        except Exception as e:
            st.error(f"Error uploading audio: {str(e)}")
            return False

    def download_audio(self, meeting_id: str) -> Optional[str]:
        """
        Download audio file from Supabase Storage to a temporary file.

        Args:
            meeting_id: UUID of the meeting

        Returns:
            Path to downloaded temporary file, or None if failed
        """
        if self.mock_mode:
            return None

        try:
            # Download from Supabase Storage
            file_name = f"{meeting_id}.mp3"
            audio_data = self.client.storage.from_("meeting-audio").download(file_name)

            # Save to temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            temp_file.write(audio_data)
            temp_file.close()

            return temp_file.name

        except Exception as e:
            # Silently fail - audio might not be stored for older meetings
            return None

    def delete_audio(self, meeting_id: str) -> bool:
        """
        Delete audio file from Supabase Storage.

        Args:
            meeting_id: UUID of the meeting

        Returns:
            True if successful, False otherwise
        """
        if self.mock_mode:
            return True

        try:
            file_name = f"{meeting_id}.mp3"
            self.client.storage.from_("meeting-audio").remove([file_name])

            # Update meeting record
            self.client.table("meetings").update({
                "audio_stored": False
            }).eq("id", meeting_id).execute()

            return True

        except Exception as e:
            # Don't show error - file might not exist
            return False

    def cleanup_old_audio(self, keep_count: int = 5) -> bool:
        """
        Delete audio files for all but the most recent meetings.
        Keeps only the last 'keep_count' meetings with audio.

        Args:
            keep_count: Number of most recent meetings to keep audio for

        Returns:
            True if successful, False otherwise
        """
        if self.mock_mode:
            return True

        try:
            # Get all meetings with audio, ordered by creation date
            result = self.client.table("meetings").select("id, audio_stored").eq("audio_stored", True).order("created_at", desc=True).execute()

            if not result.data or len(result.data) <= keep_count:
                # Nothing to clean up
                return True

            # Delete audio for meetings beyond the keep_count
            meetings_to_cleanup = result.data[keep_count:]

            for meeting in meetings_to_cleanup:
                meeting_id = meeting.get("id")
                if meeting_id:
                    self.delete_audio(meeting_id)

            return True

        except Exception as e:
            st.error(f"Error cleaning up old audio: {str(e)}")
            return False

    # ==================== FULL MEETING LOAD ====================

    def load_full_meeting(self, meeting_id: str) -> Optional[dict]:
        """
        Load all data for a meeting in one call.

        Args:
            meeting_id: UUID of the meeting

        Returns:
            Dictionary containing all meeting data or None
        """
        if self.mock_mode:
            return None

        try:
            meeting = self.get_meeting(meeting_id)
            if not meeting:
                return None

            transcript = self.get_transcript(meeting_id)
            intelligence = self.get_intelligence(meeting_id)
            speakers = self.get_speakers(meeting_id)
            chat_history = self.get_chat_history(meeting_id)
            bylaws = self.get_bylaws(meeting_id)

            return {
                "meeting": meeting,
                "transcript": transcript,
                "intelligence": intelligence,
                "speakers": speakers,
                "chat_history": chat_history,
                "bylaws_text": bylaws
            }

        except Exception as e:
            st.error(f"Error loading full meeting: {str(e)}")
            return None


def get_supabase_manager() -> SupabaseManager:
    """
    Factory function to get a SupabaseManager instance.
    Reads credentials from Streamlit secrets.

    Returns:
        SupabaseManager instance
    """
    url = st.secrets.get("SUPABASE_URL", "")
    key = st.secrets.get("SUPABASE_KEY", "")

    return SupabaseManager(url=url, key=key)
