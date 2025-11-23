# core/followup.py
from llm.llm_providers import generate_response

FOLLOWUP_SYS = "You are an interviewer asking a short targeted follow-up question."

def generate_followup_with_llm(question: str, answer: str, follow_up_type: str, role: str) -> str:
    # unchanged existing logic
    if follow_up_type == "hint":
        return generate_hint_with_llm(question, answer, role)

    prompt = (
        f"{FOLLOWUP_SYS}\nRole: {role}\nOriginal question: {question}\n"
        f"Candidate answer: {answer}\nFollow-up focus: {follow_up_type}\n\n"
        "Produce one short follow-up question (1-2 sentences). Output plain text only."
    )
    messages = [
        {"role":"system","content":FOLLOWUP_SYS},
        {"role":"user","content":prompt}
    ]
    out = generate_response(messages, max_tokens=80, temperature=0.25)
    return out.strip()

# Hint generator (already provided) - returns hint + re-ask (single string)
HINT_SYS = "You are an interviewer providing a small hint to help the candidate, but do NOT give away the answer."

def generate_hint_with_llm(question: str, answer: str, role: str) -> str:
    prompt = (
        f"{HINT_SYS}\nRole: {role}\nQuestion: {question}\nCandidate said: {answer}\n\n"
        "Provide one short hint (<= 18 words) that nudges the candidate toward thinking of the right area, "
        "without giving the actual answer. Then re-ask the original question as a short sentence. Output plain text only."
    )
    messages = [
        {"role":"system","content":HINT_SYS},
        {"role":"user","content":prompt}
    ]
    out = generate_response(messages, max_tokens=120, temperature=0.25)
    return out.strip()

# New: rephrase the question / paraphrase for clarity
REPHRASE_SYS = "You are an interviewer who can paraphrase a question simply and concisely."

def generate_rephrase_with_llm(question: str, role: str) -> str:
    prompt = (
        f"{REPHRASE_SYS}\nRole: {role}\nQuestion: {question}\n\n"
        "Paraphrase this question in one short sentence (<= 20 words) so a candidate who didn't understand can try again. "
        "Output plain text only."
    )
    messages = [
        {"role":"system","content":REPHRASE_SYS},
        {"role":"user","content":prompt}
    ]
    out = generate_response(messages, max_tokens=80, temperature=0.2)
    return out.strip()