# core/heuristics.py
import re
from typing import Tuple
from llm.llm_providers import generate_response

# minimal stopword list to remove common words when computing overlap
STOPWORDS = {
    "the","is","a","an","and","or","of","in","to","for","on","that","this","it","with",
    "as","are","was","were","be","by","from","at","which","but","not","you","your","i"
}

GREETING_PATTERNS = [
    r"^\s*(hi|hello|hey|yo|hiya)[\!\.\,\s]*$",
    r"^\s*(thanks|thank you)[\!\.\,\s]*$",
    r"^\s*(ok|okay|sure)[\!\.\,\s]*$",
    r"^\s*(yes|no)[\!\.\,\s]*$"
]
GREETING_REGEX = re.compile("|".join(GREETING_PATTERNS), flags=re.I)

REFUSE_PATTERNS = [
    r"\bi don('?t| not) know\b",
    r"\bnot sure\b",
    r"\bno idea\b",
    r"\bi'll pass\b",
    r"\bi will pass\b",
    r"\bprefer not to answer\b",
    r"\bi can't answer\b",
    r"\bi cannot answer\b",
    r"\bi dont want to answer\b",
    r"\bi don't want to answer\b",
    r"\bi dont want to\b",
    r"\bi don't want to\b",
    r"\bi wont answer\b",
    r"\bi won't answer\b",
    r"\bi will not answer\b",
    r"\bskip this\b",
    r"\bi cant answer that\b",
    r"\bi can't answer that\b"
]
REFUSE_REGEX = re.compile("|".join(REFUSE_PATTERNS), flags=re.I)

# Partial / hint request patterns (unchanged)
PARTIAL_PATTERNS = [
    r"\bkind of\b",
    r"\bsort of\b",
    r"\bi remember\b",
    r"\bi know the (idea|concept)\b",
    r"\bneed a hint\b",
    r"\bcan you give me a hint\b",
    r"\bnot the details\b",
    r"\bneed (a )?clue\b",
    r"\bcan you rephrase\b",
    r"\bcan you explain\b"
]
PARTIAL_REGEX = re.compile("|".join(PARTIAL_PATTERNS), flags=re.I)

def _tokenize_and_filter(text: str):
    # simple tokenizer: split on non-word chars and lowercase, remove stopwords
    tokens = re.findall(r"\w+", text.lower())
    return [t for t in tokens if t not in STOPWORDS]

def heuristic_relation_check(question: str, answer: str, overlap_threshold: float = 0.2) -> str:
    """
    Fast heuristic:
    - If answer is empty -> 'unrelated'
    - If matches greeting -> 'unrelated' (treat greetings as unrelated)
    - If very short (<=2 tokens) and not numeric -> 'unrelated_ambiguous' (ask clarifying)
    - Compute overlap of content tokens: overlap / len(question_tokens)
      -> if overlap < threshold => 'unrelated'
      -> else => 'related'
    Returns: 'related'|'unrelated'|'ambiguous'
    """
    if not answer or answer.strip() == "":
        return "unrelated"
    
    # direct refuse check first (cheap)
    if REFUSE_REGEX.search(answer):
        return "refuse"

    # greetings/short non-answers
    if GREETING_REGEX.search(answer):
        return "unrelated"

    # very short replies (1-2 tokens) are ambiguous/unrelated
    ans_tokens = _tokenize_and_filter(answer)
    if len(ans_tokens) <= 2:
        # could be "I know" or "sure" or a one-word real answer; return ambiguous for LLM fallback or clarification path
        return "ambiguous"

    q_tokens = _tokenize_and_filter(question)
    if not q_tokens:
        return "ambiguous"

    overlap = set(q_tokens).intersection(set(ans_tokens))
    overlap_ratio = len(overlap) / max(1, len(q_tokens))

    if overlap_ratio < overlap_threshold:
        return "unrelated"

    return "related"

# LLM fallback classifier prompt (low temperature, deterministic)
CLASSIFIER_SYS = "You are a concise classifier that decides whether a candidate's reply is related to the interview question."

def classify_relation_with_llm(question: str, answer: str) -> dict:
    """
    Ask LLM to decide whether the answer is related to the question.
    Returns a dict: {"related": true/false/"ambiguous", "reason": "..."}
    """
    prompt = (
        f"{CLASSIFIER_SYS}\n\nQuestion: {question}\nCandidate reply: {answer}\n\n"
        "Return JSON only: {\"related\": true|false|\"ambiguous\", \"reason\": \"one-line reason\"}."
    )
    messages = [
        {"role": "system", "content": CLASSIFIER_SYS},
        {"role": "user", "content": prompt}
    ]
    raw = generate_response(messages, max_tokens=120, temperature=0.0)
    # robust parse
    import json, re
    try:
        return json.loads(raw)
    except Exception:
        m = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    # fallback ambiguous
    return {"related": "ambiguous", "reason": "could not parse classifier output"}

# Backwards-compatible detect_knowledge_intent (used elsewhere)
def detect_knowledge_intent(answer_text: str) -> str:
    if not answer_text or answer_text.strip() == "":
        return "unknown"
    text = answer_text.strip().lower()
    if REFUSE_REGEX.search(text):
        return "refuse"
    if PARTIAL_REGEX.search(text):
        return "partial"
    if GREETING_REGEX.search(text):
        return "greeting"
    if re.search(r"\bi don('?t| not) know\b|\bno idea\b", text, flags=re.I):
        return "unknown"
    return "ambiguous"