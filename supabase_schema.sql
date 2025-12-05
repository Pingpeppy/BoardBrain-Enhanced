-- BoardBrain Supabase Schema
-- Run this SQL in your Supabase SQL Editor to set up the database

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ==================== MEETINGS TABLE ====================
-- Main table storing meeting metadata
CREATE TABLE IF NOT EXISTS meetings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    video_filename TEXT NOT NULL,
    meeting_date DATE,
    duration_minutes INTEGER DEFAULT 0,
    speakers_count INTEGER DEFAULT 0,
    bylaws_text TEXT,
    audio_stored BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for faster queries by date
CREATE INDEX IF NOT EXISTS idx_meetings_created_at ON meetings(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_meetings_meeting_date ON meetings(meeting_date DESC);

-- ==================== TRANSCRIPTS TABLE ====================
-- Stores raw transcript data with utterances
CREATE TABLE IF NOT EXISTS transcripts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    meeting_id UUID NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    raw_text TEXT,
    utterances JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(meeting_id)
);

-- Index for faster lookups by meeting
CREATE INDEX IF NOT EXISTS idx_transcripts_meeting_id ON transcripts(meeting_id);

-- ==================== INTELLIGENCE TABLE ====================
-- Stores extracted meeting intelligence (motions, action items, summary, etc.)
CREATE TABLE IF NOT EXISTS intelligence (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    meeting_id UUID NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    meeting_date DATE,
    summary TEXT,
    motions JSONB DEFAULT '[]'::jsonb,
    action_items JSONB DEFAULT '[]'::jsonb,
    sentiment_analysis JSONB DEFAULT '{}'::jsonb,
    topic_trends JSONB DEFAULT '[]'::jsonb,
    financial_impact JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(meeting_id)
);

-- Index for faster lookups by meeting
CREATE INDEX IF NOT EXISTS idx_intelligence_meeting_id ON intelligence(meeting_id);

-- ==================== SPEAKERS TABLE ====================
-- Stores speaker information and name mappings
CREATE TABLE IF NOT EXISTS speakers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    meeting_id UUID NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    original_label TEXT NOT NULL,
    assigned_name TEXT,
    speaking_time_ms INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for faster lookups by meeting
CREATE INDEX IF NOT EXISTS idx_speakers_meeting_id ON speakers(meeting_id);

-- ==================== CHAT MESSAGES TABLE ====================
-- Stores chat history for each meeting
CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    meeting_id UUID NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for faster lookups and ordering
CREATE INDEX IF NOT EXISTS idx_chat_messages_meeting_id ON chat_messages(meeting_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON chat_messages(meeting_id, created_at);

-- ==================== ROW LEVEL SECURITY (Optional) ====================
-- Enable RLS if you want to restrict access per user
-- Uncomment and modify these policies based on your auth setup

-- ALTER TABLE meetings ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE transcripts ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE intelligence ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE speakers ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;

-- Example policy for authenticated users (adjust as needed):
-- CREATE POLICY "Users can view their own meetings"
--     ON meetings FOR SELECT
--     USING (auth.uid() = user_id);

-- ==================== UPDATED_AT TRIGGER ====================
-- Function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to tables with updated_at column
DROP TRIGGER IF EXISTS update_meetings_updated_at ON meetings;
CREATE TRIGGER update_meetings_updated_at
    BEFORE UPDATE ON meetings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_transcripts_updated_at ON transcripts;
CREATE TRIGGER update_transcripts_updated_at
    BEFORE UPDATE ON transcripts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_intelligence_updated_at ON intelligence;
CREATE TRIGGER update_intelligence_updated_at
    BEFORE UPDATE ON intelligence
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ==================== HELPFUL VIEWS (Optional) ====================
-- View for listing meetings with basic stats
CREATE OR REPLACE VIEW meeting_summary AS
SELECT
    m.id,
    m.video_filename,
    m.meeting_date,
    m.duration_minutes,
    m.speakers_count,
    m.created_at,
    i.summary,
    CASE
        WHEN i.motions IS NULL THEN 0
        WHEN jsonb_typeof(i.motions) = 'array' THEN jsonb_array_length(i.motions)
        ELSE 0
    END as motion_count,
    CASE
        WHEN i.action_items IS NULL THEN 0
        WHEN jsonb_typeof(i.action_items) = 'array' THEN jsonb_array_length(i.action_items)
        ELSE 0
    END as action_item_count
FROM meetings m
LEFT JOIN intelligence i ON m.id = i.meeting_id
ORDER BY m.created_at DESC;

-- ==================== GRANT PERMISSIONS ====================
-- Grant permissions to the anon and authenticated roles
-- Adjust based on your security requirements

GRANT SELECT, INSERT, UPDATE, DELETE ON meetings TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON transcripts TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON intelligence TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON speakers TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON chat_messages TO anon, authenticated;
GRANT SELECT ON meeting_summary TO anon, authenticated;
