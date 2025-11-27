# core/evaluator.py
import json
from llm.llm_providers import generate_response
from core.heuristics import detect_knowledge_intent

EVAL_SYS = ("You are an objective interview evaluator. For each candidate answer produce a JSON object and nothing else.\n"
            "Return fields: clarity(1-5), structure(1-5), technical_depth(1-5), relevance(1-5), "
            "needs_follow_up(true/false), follow_up_type(one of clarity,depth,example,none), comments (<=30 words).")

# small classifier prompt used only when heuristics return 'unknown_ambiguous'
CLASSIFY_SYS = ("You are a concise classifier for candidate intent. Answer with a single JSON: "
                "{\"knowledge_intent\": \"known|partial|unknown|refuse\", \"reason\": \"short reason\" }")

def classify_knowledge_with_llm(answer: str, question: str = "", role: str = "") -> dict:
    prompt = (
        f"{CLASSIFY_SYS}\n\nRole: {role}\nQuestion: {question}\nCandidate answer: {answer}\n\n"
        "Interpret the candidate's answer and reply with the JSON only."
    )
    messages = [
        {"role": "system", "content": CLASSIFY_SYS},
        {"role": "user", "content": prompt}
    ]
    raw = generate_response(messages, max_tokens=100, temperature=0.0)
    try:
        return json.loads(raw)
    except Exception:
        # try to find a JSON substring
        import re
        m = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    # fallback conservative
    return {"knowledge_intent": "unknown", "reason": "could not parse classifier output"}

def evaluate_answer_with_llm(question: str, answer: str, role: str, context: str = "", skills=None,) -> dict:
    # First, use heuristics to detect knowledge/refusal
    kb_intent = detect_knowledge_intent(answer)
    knowledge_obj = {"knowledge_intent_heuristic": kb_intent}
    skills_text = ", ".join(skills) if skills else "not specified"


    # If ambiguous, fall back to LLM classifier
    if kb_intent == "unknown_ambiguous":
        try:
            cls = classify_knowledge_with_llm(answer, question, role)
            # normalize
            if isinstance(cls, dict) and "knowledge_intent" in cls:
                knowledge_obj["knowledge_intent_llm"] = cls["knowledge_intent"]
                kb = cls["knowledge_intent"]
            else:
                kb = "unknown"
                knowledge_obj["knowledge_intent_llm"] = "unknown"
        except Exception:
            kb = "unknown"
            knowledge_obj["knowledge_intent_llm"] = "unknown"
    else:
        kb = kb_intent

    # Now perform the standard evaluation
    prompt = (
        f"{EVAL_SYS}\n\n"
        f"Role: {role}\n"
        f"Target skills: {skills_text}\n" 
        f"Question: {question}\n"
        f"Answer: {answer}\n"
        f"Context: {context}\n\n"
        "Return only valid JSON."
    )

    messages = [
        {"role": "system", "content": EVAL_SYS},
        {"role": "user", "content": prompt}
    ]

    raw_eval = generate_response(messages, max_tokens=300, temperature=0.0)
    try:
        data = json.loads(raw_eval)
    except Exception:
        # extract JSON block if possible
        import re
        m = re.search(r"\{.*\}", raw_eval, flags=re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(0))
            except Exception:
                data = None
        else:
            data = None

    if not data:
        data = {
            "clarity": 3, "structure": 3,
            "technical_depth": 0 if role.lower() != "software_engineer" else 3,
            "relevance": 3, "needs_follow_up": False, "follow_up_type": "none",
            "comments": "Could not parse model output; default neutral scores."
        }

    # attach knowledge intent into eval for controller decisions
    data["knowledge_intent"] = kb
    data.update(knowledge_obj)
    return data
