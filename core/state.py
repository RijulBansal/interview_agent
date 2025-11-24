# core/state.py
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class InterviewState:
    role: str = None
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