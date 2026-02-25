# Agentic Workflows for BoardBrain — Brainstorm

**Date:** 2026-02-25
**Author:** AI-assisted design session

---

## What "Agentic" Means Here

BoardBrain currently runs a linear, single-pass pipeline:

```
video → audio → transcript → extract_intelligence() → static display
```

Every AI call is a one-shot prompt. The model receives a large block of text,
produces a response, and stops. There is no iteration, no tool use, and no
cross-meeting memory.

**Agentic patterns** introduce three new capabilities:

| Capability | What It Enables |
|------------|----------------|
| **Tool use / function calling** | Model decides what data to look up; gets targeted results instead of a full text dump |
| **Multi-step reasoning loops** | Model reflects on intermediate results and continues until the goal is met |
| **Cross-meeting memory** | Agent queries historical records and surfaces continuity between meetings |

These patterns require no architectural overhaul — they slot into the existing
`processor.py` / `app.py` separation, respect mock mode, and extend the Supabase
data layer that already exists.

---

## Brainstorm: All Candidate Workflows

### Tier 1 — High Impact, Implementable Now

---

#### 1. Tool-Using Chat Agent

**Current state:** `chat_with_meeting()` dumps the entire formatted transcript
plus all intelligence data into a single system prompt (potentially 30,000+ tokens)
and makes one API call. The model pattern-matches over a huge string with no ability
to look things up. Compound or cross-referencing questions frequently produce
hallucinations or incomplete answers.

**Agentic pattern:** OpenAI function calling with a bounded iteration loop (max 5
calls). The model is given a compact system prompt describing the meeting's structure
and a set of callable tools. It decides which tool to call, receives a targeted
result, and iterates until it can formulate a grounded answer.

**Tools:**
- `search_transcript(query, speaker?)` — fulltext search over utterances, returns
  top-N matching segments with speaker names and `[MM:SS]` timestamps
- `get_motion_details(motion_index)` — returns one motion object (proposer,
  seconder, vote outcome, text) by index
- `list_action_items(speaker?)` — returns action items, optionally filtered to
  one person
- `get_financial_summary()` — returns the financial_impact list and computed total
  potential spend

**Example query this unlocks:** "What did the treasurer say about the reserve fund
and what were they assigned to do?" — currently requires the model to hold the
entire transcript in mind; with tools, it calls `search_transcript("reserve fund",
speaker="Treasurer")` and `list_action_items(speaker="Treasurer")` and cites
exact timestamps.

**Implementation surface:**
- `processor.py`: 4 pure tool-implementation functions + `chat_with_meeting_agent()`
  orchestrator that runs the loop; returns `(answer_str, tool_call_log_list)`
- `app.py`: Replace the `chat_with_meeting()` call; add "Show Agent Reasoning"
  sidebar toggle; render optional tool trace expander below each chat response
- No schema changes. No new dependencies. Mock mode: return `MOCK_AGENT_CHAT_RESPONSE`
  with empty log.

**Why this is the highest priority:** It improves every single chat interaction for
every user. The existing `chat_with_meeting()` can be kept as a fallback; the agent
replaces it transparently.

---

#### 2. Cross-Meeting Action Item Continuity Agent

**Current state:** Action items are extracted per-meeting and stored in the
`intelligence` table as a JSONB blob. There is no way to know whether an item
assigned three months ago was ever completed. Each meeting loads in isolation.

**Agentic pattern:** At results-load time, an agent queries the Supabase
`action_item_tracker` table (new, flat) for open items from prior meetings assigned
to speakers present in the current meeting. It then runs a focused GPT-4o prompt
to detect whether any current-meeting transcript passages appear to resolve those
prior items. The result surfaces on the Dashboard as a "Carried Forward" panel.
The human must click a button to confirm resolution — the agent never auto-updates
the database.

**Schema addition required (one new table):**
```sql
CREATE TABLE IF NOT EXISTS action_item_tracker (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    meeting_id UUID NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    meeting_date DATE,
    task_description TEXT NOT NULL,
    assigned_to TEXT,
    due_date_inference TEXT,
    status TEXT DEFAULT 'open' CHECK (status IN ('open', 'resolved', 'superseded')),
    resolved_in_meeting_id UUID REFERENCES meetings(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Implementation surface:**
- `supabase_schema.sql`: Add `action_item_tracker` table + indexes + grants
- `processor.py`: `sync_action_items_to_tracker()` (write flat records on save) +
  `analyze_action_item_continuity()` (LLM detection of resolutions)
- `database.py`: `get_open_action_items_for_speakers()` +
  `mark_action_items_resolved()` on `SupabaseManager`
- `app.py`: Lazy-load continuity check at results entry; render panel in Dashboard
  tab; "Mark Resolved" button; reset state on Start Over

**Human-in-the-loop checkpoints:**
1. LLM suggests likely-resolved items — user confirms with a button click
2. Prior items shown as a table before new decisions — user sees context,
   no action required

**Why this is #2:** Directly solves the accountability gap that HOA boards care
most about. "Did Bill ever get those contractor bids?" becomes answerable
automatically, not by manually cross-referencing meeting minutes.

---

#### 3. Compliance Audit Agent

**Current state:** `extract_intelligence()` does a single-pass Robert's Rules check
embedded in the main extraction prompt. The output is a one-line note in the summary
text field. It checks quorum and seconding but does not iterate over each motion
individually.

**Agentic pattern:** After intelligence extraction, a secondary agent iterates over
each motion and runs a focused validation prompt for that motion only (has a mover?
seconder? clear vote count? proper amendment handling?). Accumulates a structured
audit report — one record per motion — with specific violation codes, severity
levels, and suggested corrections.

**Implementation surface:**
- `processor.py`: `audit_motion_compliance(motion, transcript_excerpt, api_key)`
  for a single motion + `run_compliance_audit(motions, transcript, api_key)` loop
- `app.py`: New "Compliance Audit" expander on Dashboard tab, or new tab if the
  report is long
- No schema changes (compliance report stored in session state; optionally written
  to the `intelligence` JSONB blob)

**Why it's Tier 1 but #3:** High value for compliance-conscious boards, but narrower
audience than chat (all users) or continuity (all boards with history).

---

### Tier 2 — High Impact, More Complex

---

#### 4. Multi-Pass Intelligence Refinement Agent

**Current state:** `extract_intelligence()` makes one GPT-4o call and accepts its
output. If the model misses a motion buried in discussion or assigns a low-confidence
label to an action item, that error propagates silently into the displayed results.

**Agentic pattern:**
1. Run standard extraction.
2. Model scores its own confidence per-field (0–1).
3. For fields below threshold (e.g., < 0.7), re-run a focused extraction prompt
   targeting only that section of the transcript.
4. Surface a "Low confidence — please review" flag on any field below the
   threshold even after refinement.
5. Optional: present uncertain items to the user for quick confirmation before saving.

**Implementation considerations:** Adds 1–3 extra API calls per meeting. Should be
opt-in (toggle in settings). Works best for long meetings where the first-pass model
may lose track of mid-meeting events.

---

#### 5. Speaker Resolution Agent

**Current state:** `suggest_speaker_names()` makes one API call, returns name
suggestions, and the user accepts or edits them manually. For boards with many
members or poor audio quality, several speakers may remain unidentified.

**Agentic pattern:**
1. First pass: extract confident name attributions (mentioned by name in the
   recording, e.g., "As Bill mentioned...").
2. Second pass: for unresolved speakers, cross-reference their topics against
   board member role descriptions (from an uploaded attendee list or roster).
3. Third pass: present only the remaining ambiguous cases to the user with
   two candidate names and a supporting quote.
4. Result: user reviews only O(few) cases rather than O(all speakers).

**Implementation considerations:** Needs an optional "Attendee Roster" upload
added to the sidebar. Could repurpose the existing `bylaws_text` upload pattern.

---

#### 6. Anomaly Detection Agent

**Current state:** Each meeting is analyzed in isolation. There is no baseline.

**Agentic pattern:** When Supabase is connected and at least 3 prior meetings
exist, run a secondary agent that:
1. Fetches summary stats from prior meetings (meeting length, speaker count,
   motion count, action item count).
2. Computes mean and standard deviation for each stat.
3. Flags the current meeting's stats that deviate by more than 1.5σ with a note
   explaining what is unusual (e.g., "This meeting had 3× the usual number of
   motions").

**Use cases:** Catching unusually short meetings that may indicate poor recording,
unusually high action item counts that suggest an overwhelmed board, quorum-near-miss
patterns.

---

#### 7. Pre-Meeting Preparation Agent

**Current state:** BoardBrain is a retrospective tool — it processes meetings after
they happen.

**Agentic pattern:** Add a "Prepare for Next Meeting" mode. When triggered, the agent:
1. Loads the last N meetings from Supabase.
2. Collects all open action items across those meetings.
3. Identifies which action items are due based on `due_date_inference` vs today.
4. Drafts a structured agenda with: Approval of last minutes → Open action item
   updates → Pending motions from tabled items → New business suggestions based on
   trend topics.
5. Exports as a Word document.

**Implementation considerations:** Requires Supabase to be connected. Should gate
on `len(prior_meetings) >= 1`. No new APIs needed — uses existing `generate_word_document()`
pattern.

---

### Tier 3 — Longer-Term / Infrastructure Dependent

| Idea | Blocker | Value When Ready |
|------|---------|-----------------|
| **Real-time transcription** | Requires AssemblyAI streaming API integration + WebSocket in Streamlit | Live meeting captioning and real-time action item extraction |
| **External task sync** | Requires OAuth or API key management for Asana / Trello / Monday | Action items flow directly into the board's existing task tracker |
| **Cross-HOA benchmarking** | Requires multi-tenant data model, anonymization pipeline | Boards can see how their meeting efficiency compares to similar HOAs |
| **Budget variance agent** | Requires accounting export integration (QuickBooks / CSV) | Auto-links financial motions to actuals at next meeting |
| **Email digest agent** | Requires SMTP / SendGrid integration | Auto-sends meeting summaries to all board members and homeowners |

---

## Prioritized Recommendations

### Implement First: Tool-Using Chat Agent

- Zero schema changes
- Immediate improvement to every chat interaction
- Fully mockable; no API keys required to develop and test
- Transparent to users (reasoning trace is optional/off by default)
- Estimated scope: ~150 lines in `processor.py`, ~40 lines in `app.py`

### Implement Second: Cross-Meeting Continuity Agent

- One schema addition (can be applied to existing Supabase project in minutes)
- Unlocks the full value of the existing Supabase investment
- Human-in-the-loop design means zero risk of accidental data changes
- Estimated scope: ~120 lines in `processor.py`, ~60 lines in `app.py`,
  ~30 lines in `database.py`

### Implement Third: Compliance Audit Agent

- No schema changes
- Iterative-per-motion pattern is straightforward to implement
- Can be added as an opt-in "Run Compliance Audit" button rather than running
  automatically on every meeting
- Estimated scope: ~80 lines in `processor.py`, ~30 lines in `app.py`

---

## Design Principles for All Implementations

1. **Mock mode first.** Every new API-calling function checks for `"dummy"` key
   before making any real call. All mock responses defined as `MOCK_*` constants.

2. **Separate concerns.** OpenAI + Supabase calls in `processor.py` / `database.py`.
   All `st.*` calls in `app.py`. This is a hard rule in CLAUDE.md.

3. **Bound all loops.** Agent iteration loops capped at `MAX_AGENT_ITERATIONS = 5`
   to prevent runaway cost. Force a final synthesis call if the cap is hit.

4. **Human in the loop for writes.** Agents may read and analyze freely, but any
   database write (e.g., marking an action item resolved) requires explicit user
   confirmation via a button click.

5. **Degrade gracefully.** If Supabase is not connected, continuity features are
   silently skipped. If OpenAI key is missing, chat returns an empty state. No
   hard failures.

6. **Try/except around every external call.** Return safe defaults. Surface errors
   via `st.error()` rather than unhandled exceptions.

---

*Generated as part of the `claude/agentic-workflows-brainstorm-qy3rh` design session.*
