# core/question_generator.py
from typing import List
import re

from llm.llm_providers import generate_response

QUESTION_SYS = (
    "You are an experienced, fair and safe interview designer. "
    "You create structured interview question sets tailored to the role and skills. "
    "Avoid any illegal, discriminatory or overly personal questions "
    "(no age, religion, marital status, politics, health, or PII)."
)


def _infer_num_questions(mode: str) -> int:
    mode = (mode or "normal").lower()
    if mode == "brief":
        return 4  # efficient user, short interview
    if mode == "deep":
        return 9  # longer, more probing
    return 6      # normal mode


def generate_question_list(role: str, mode: str, skills: List[str]) -> List[str]:
    """
    Generate an ordered list of interview questions based on role, mode and skills.
    """
    skills_text = ", ".join(skills) if skills else "general skills for this role"
    num_questions = _infer_num_questions(mode)

    prompt = f"""
You are designing a structured interview.

Role: {role or "unspecified"}
Interview mode: {mode or "normal"}  (brief | normal | deep)
Focus skills / topics: {skills_text}

Design exactly {num_questions} main interview questions.

Guidelines:
- For BRIEF mode: Ask concise, high-signal questions that can be answered in ~1–2 minutes.
- For NORMAL mode: Mix behavioural and technical/role-specific questions, answerable in ~2–3 minutes.
- For DEEP mode: Ask more probing, scenario-based questions that explore trade-offs and reasoning.
- Use clear, neutral language.
- Do NOT include answers, hints, or commentary.
- Do NOT ask for any personally identifiable information (no full name, address, phone, email, ID numbers, etc.).
- Do NOT ask about age, gender, religion, politics, health, or family status.
- Output ONLY a numbered list in this format:

1. First question...
2. Second question...
...

Now output the list.
""".strip()

    messages = [
        {"role": "system", "content": QUESTION_SYS},
        {"role": "user", "content": prompt},
    ]

    raw = generate_response(messages, max_tokens=700, temperature=0.35)

    # Parse numbered list
    questions: List[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^\d+[\).\s-]+(.+)", line)
        if m:
            q = m.group(1).strip()
            if q:
                questions.append(q)

    # Fallback: if parsing failed, treat whole output as one question
    if not questions and raw.strip():
        questions = [raw.strip()]

    return questions
