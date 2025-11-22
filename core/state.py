# core/state.py
from dataclasses import dataclass, field
from typing import List, Dict, Any

@dataclass
class InterviewState:
    role: str = None
    current_question_index: int = 0
    questions: List[str] = field(default_factory=list)
    answers: List[str] = field(default_factory=list)
    evaluations: List[Dict[str,Any]] = field(default_factory=list)
    stage: str = "not_started"  # not_started | in_progress | finished
