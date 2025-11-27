# core/final_summary.py
import json
from llm.llm_providers import generate_response
from typing import List, Dict, Any, Optional

SUMMARY_SYS = "You are an expert interview coach. Analyze the session and produce a structured summary."

def generate_final_feedback_with_llm(
    role: str,
    questions: List[str],
    answers: List[str],
    evaluations: List[Dict[str, Any]],
    skills: Optional[List[str]] = None,
) -> Dict[str, Any]:
    # pack inputs
    skills_text = ", ".join(skills) if skills else "not specified"

    input_blob = {
        "role": role,
        "qa": list(zip(questions, answers)),
        "evaluations": evaluations,
        "skills": skills or [],
    }
    prompt = (
        f"{SUMMARY_SYS}\n\nRole: {role}\n\n"
        f"Target skills: {skills_text}\n\n"
        f"Questions & Answers: {questions}\n\n"
        f"Per-answer evaluations: {json.dumps(evaluations)}\n\n"
        "Return JSON with overall_scores, strengths, weaknesses, top_tips, and a short paragraph (<=100 words)."
    )
    messages = [
        {"role":"system","content":SUMMARY_SYS},
        {"role":"user","content":prompt}
    ]
    raw = generate_response(messages, max_tokens=600, temperature=0.0)
    # try to extract JSON first
    try:
        j = json.loads(raw)
        return {"json": j, "text": ""}
    except Exception:
        import re
        m = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if m:
            try:
                j = json.loads(m.group(0))
                # remove json from text
                text = raw.replace(m.group(0), "").strip()
                return {"json": j, "text": text}
            except Exception:
                pass
    # fallback: return text as paragraph only
    return {"json": None, "text": raw}
