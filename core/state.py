# core/state.py
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class InterviewState:
    role: str = None
    mode: str = "normal"  # "brief" | "normal" | "deep"
    current_question_index: int = 0
    questions: List[str] = field(default_factory=list)
    answers: List[str] = field(default_factory=list)
    evaluations: List[Dict[str, Any]] = field(default_factory=list)
    stage: str = "not_started"  # not_started | in_progress | finished

    # NEW: store the follow-up question text here when the agent issues a follow-up
    # so that the next incoming user reply is interpreted as an answer to this follow-up.
    pending_followup: Optional[str] = None        # current follow-up question text
    followup_depth: int = 0                       # how many nested followups asked for current main Q
    MAX_FOLLOWUP_DEPTH: int = 2                   # configurable per-session value
    followup_history: List[Dict[str,Any]] = field(default_factory=list)  # records followups asked and answers
    topic_escape_count: int = 0

    # NEW: short-term memory list (most recent first)
    stm: List[Dict[str, Any]] = field(default_factory=list)  # e.g. {"q": "...", "a": "...", "metadata": {...}}

    # NEW: long-term memory metadata (summaries / pointers)
    ltm_index_path: Optional[str] = None  # path to vector DB or saved embeddings
    ltm_summary: List[Dict[str, Any]] = field(default_factory=list)  # compressed summaries if no vector DB

    # NEW: configuration / params
    MAX_STM_ITEMS: int = 10
    MAX_LTM_SUMMARIES: int = 200