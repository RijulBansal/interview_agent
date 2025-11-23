# core/final_summary.py
import json
from llm.llm_providers import generate_response

SUMMARY_SYS = "You are an expert interview coach. Analyze the session and produce a structured summary."

def generate_final_feedback_with_llm(role: str, questions: list, answers: list, evaluations: list) -> dict:
    # pack inputs
    input_blob = {
        "role": role,
        "qa": list(zip(questions, answers)),
        "evaluations": evaluations
    }
    prompt = (
        f"{SUMMARY_SYS}\n\nRole: {role}\n\n"
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
