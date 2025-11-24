# core/controller.py

from core.state import InterviewState
from core.heuristics import heuristic_relation_check, classify_relation_with_llm
from core.evaluator import evaluate_answer_with_llm
from core.followup import (
    generate_rephrase_with_llm,
    generate_hint_with_llm,
    generate_followup_with_llm
)
from core.heuristics import detect_knowledge_intent
    
def handle_user_answer(state: InterviewState, user_answer: str):

    #debugging prints
    print("\n[DEBUG] New user answer received:", user_answer)
    print("[DEBUG] pending_followup =", state.pending_followup)

    """
    Core agent loop:
      1) Heuristic + LLM detection for unrelated responses
      2) Clarification / rephrase / fallback skip
      3) Explicit unknown/refuse handling
      4) Partial knowledge -> hint + ask again
      5) Full evaluation + follow-ups
      6) Move to next / finish
    """

    idx = state.current_question_index
    question = state.questions[idx]

    # --- Ensure evaluations[index] exists ---
    if idx >= len(state.evaluations):
        state.evaluations.append({"question_index": idx})

    # --- Always store raw user response ---
    state.answers.append(user_answer)
    
    # === Detect whether this is answering a follow-up question ===
    is_followup = False
    if getattr(state, "pending_followup", None):
        # This reply was intended to answer the previously issued follow-up question
        question_being_answered = state.pending_followup
        is_followup = True
        # clear pending followup now that we're consuming it
        state.pending_followup = None
    else:
        # normal main question flow
        question_being_answered = state.questions[idx]

    # === If this is a follow-up answer, SKIP unrelated detection and go straight to evaluation ===
    if is_followup:

        #debugging print
        print("[DEBUG] FOLLOW-UP MODE ACTIVE — skipping unrelated detection")

        # Evaluate the answer in the context of the follow-up question
        eval_json_preview = evaluate_answer_with_llm(question_being_answered, user_answer, state.role)
        # store the evaluation under the current question's slot
        state.evaluations[idx].update(eval_json_preview)

        # follow-up answers may themselves request another follow-up
        if eval_json_preview.get("needs_follow_up") and eval_json_preview.get("follow_up_type") != "none":
            follow_up_q = generate_followup_with_llm(
                question=question_being_answered,
                answer=user_answer,
                follow_up_type=eval_json_preview.get("follow_up_type"),
                role=state.role
            )
            # IMPORTANT: set pending_followup so next user reply is mapped to this follow-up
            state.pending_followup = follow_up_q
            state.evaluations[idx]["follow_up_asked"] = True
            return {"action": "ask_follow_up", "payload": follow_up_q, "state": state}

        # if not asking another follow-up, proceed to next main question or finish
        if state.current_question_index + 1 >= len(state.questions):
            state.stage = "finished"
            from core.final_summary import generate_final_feedback_with_llm
            summary = generate_final_feedback_with_llm(state.role, state.questions, state.answers, state.evaluations)
            return {"action": "finish", "payload": summary, "state": state}

        state.current_question_index += 1
        next_q = state.questions[state.current_question_index]
        return {"action": "ask_question", "payload": next_q, "state": state}

    #debugging print
    print("[DEBUG] MAIN QUESTION MODE — running unrelated detection on:", question_being_answered)

    # ==============================================================
    # STEP 0 — EXPLICIT REFUSAL ("I don’t want to answer") or "I don't know"
    # ==============================================================

    kb_intent_quick = detect_knowledge_intent(user_answer).lower()

    if kb_intent_quick in ("refuse", "unknown"):
        # record skip
        state.evaluations[idx].update({
            "knowledge_intent": kb_intent_quick,
            "skipped_due_to_refusal": True
        })

        # Move to next or finish
        if state.current_question_index + 1 >= len(state.questions):
            state.stage = "finished"
            from core.final_summary import generate_final_feedback_with_llm
            summary = generate_final_feedback_with_llm(
                state.role, state.questions, state.answers, state.evaluations
            )
            return {"action": "finish", "payload": summary, "state": state}
        else:
            state.current_question_index += 1
            next_q = state.questions[state.current_question_index]
            return {"action": "ask_question", "payload": next_q, "state": state}

    # ==============================================================
    #   STEP 1 — Detect if the response is RELATED or UNRELATED
    # ==============================================================

    relation = heuristic_relation_check(question_being_answered, user_answer)  # related | unrelated | ambiguous

    # Ambiguous → use LLM fallback to classify relationship
    if relation == "ambiguous":
        cls = classify_relation_with_llm(question_being_answered, user_answer)
        rel = cls.get("related", "ambiguous")

        # Normalize bool → string
        if isinstance(rel, bool):
            relation = "related" if rel else "unrelated"
        else:
            relation = rel   # could be "ambiguous", treat as unrelated-ish if needed

    # ==============================================================
    #   STEP 2 — Handle UNRELATED responses (including greetings)
    # ==============================================================

    if relation == "unrelated":
        clarity_count = state.evaluations[idx].get("clarity_offered", 0)

        # First unrelated → clarify
        if clarity_count == 0:
            rephrase = generate_rephrase_with_llm(question_being_answered, state.role)
            state.evaluations[idx]["clarity_offered"] = 1
            clarification_text = (
                f"It seems your reply wasn't related to the question.\n"
                f"Did you understand it?\n\n"
                f"I can rephrase it as:\n\"{rephrase}\"\n\n"
                f"Would you like the rephrased version or the original?"
            )
            return {
                "action": "clarify",
                "payload": clarification_text,
                "state": state
            }

        # Second unrelated → re-ask the SAME question once
        if clarity_count == 1:
            state.evaluations[idx]["clarity_offered"] = 2
            return {
                "action": "ask_question",
                "payload": question_being_answered,
                "state": state
            }

        # Third unrelated → SKIP to next question
        if clarity_count >= 2:
            state.evaluations[idx]["skipped_due_to_unrelated_replies"] = True

            # End if last question
            if state.current_question_index + 1 >= len(state.questions):
                from core.final_summary import generate_final_feedback_with_llm
                state.stage = "finished"
                summary = generate_final_feedback_with_llm(
                    state.role, state.questions, state.answers, state.evaluations
                )
                return {"action": "finish", "payload": summary, "state": state}

            # Move to next question
            state.current_question_index += 1
            next_q = state.questions[state.current_question_index]
            return {"action": "ask_question", "payload": next_q, "state": state}

    # ==============================================================
    #   STEP 3 — Handle explicit "I don't know" / "I'll pass"
    # ==============================================================

    # Detect explicit knowledge intent inside evaluator
    # (We call evaluator to get knowledge intent FIRST)
    eval_json_preview = evaluate_answer_with_llm(
        question=question_being_answered,
        answer=user_answer,
        role=state.role
    )
    knowledge_intent = eval_json_preview.get("knowledge_intent", "").lower()

    if knowledge_intent in ("refuse", "unknown"):

        state.evaluations[idx].update(eval_json_preview)
        state.evaluations[idx]["skipped"] = True

        # End if last question
        if state.current_question_index + 1 >= len(state.questions):
            from core.final_summary import generate_final_feedback_with_llm
            state.stage = "finished"
            summary = generate_final_feedback_with_llm(
                state.role, state.questions, state.answers, state.evaluations
            )
            return {"action": "finish", "payload": summary, "state": state}

        # Move on
        state.current_question_index += 1
        next_q = state.questions[state.current_question_index]
        return {"action": "ask_question", "payload": next_q, "state": state}

    # ==============================================================
    #   STEP 4 — Partial knowledge → Give hint + ask question again
    # ==============================================================

    if knowledge_intent == "partial":
        state.evaluations[idx].update(eval_json_preview)
        state.evaluations[idx]["hint_offered"] = state.evaluations[idx].get("hint_offered", 0) + 1

        hint = generate_hint_with_llm(question_being_answered, user_answer, state.role)
        return {"action": "ask_follow_up", "payload": hint, "state": state}

    # ==============================================================
    #   STEP 5 — Normal evaluation + follow-up logic
    # ==============================================================

    eval_json = eval_json_preview
    state.evaluations[idx].update(eval_json)

    # If needs follow-up → ask it
    if eval_json.get("needs_follow_up") and eval_json.get("follow_up_type") != "none":
        follow_up_q = generate_followup_with_llm(
            question=question_being_answered,
            answer=user_answer,
            follow_up_type=eval_json.get("follow_up_type"),
            role=state.role
        )
    
        # MULTI-TURN FOLLOWUP DEPTH CONTROL
        if state.followup_depth >= state.MAX_FOLLOWUP_DEPTH:
            # reached max depth — record, then move to next question
            state.evaluations[idx].setdefault("note", "max_followup_depth_reached")

            # go to next main question
            if state.current_question_index + 1 >= len(state.questions):
                state.stage = "finished"
                from core.final_summary import generate_final_feedback_with_llm
                summary = generate_final_feedback_with_llm(
                    state.role, state.questions, state.answers, state.evaluations
                )
                return {"action": "finish", "payload": summary, "state": state}
            else:
                state.current_question_index += 1
                next_q = state.questions[state.current_question_index]
                state.followup_depth = 0   # reset depth
                return {"action": "ask_question", "payload": next_q, "state": state}

        # otherwise increase depth and ask next follow-up
        state.followup_depth += 1
        state.pending_followup = follow_up_q

        # record follow-up in history
        from datetime import datetime
        state.followup_history.append({
            "depth": state.followup_depth,
            "question": follow_up_q,
            "asked_at": datetime.utcnow().isoformat()
        })


        return {
            "action": "ask_follow_up",
            "payload": follow_up_q,
            "state": state
        }

    # ==============================================================
    #   STEP 6 — Go to next question or finish
    # ==============================================================

    # Last question?
    if state.current_question_index + 1 >= len(state.questions):
        from core.final_summary import generate_final_feedback_with_llm
        state.stage = "finished"
        summary = generate_final_feedback_with_llm(
            state.role, state.questions, state.answers, state.evaluations
        )
        return {"action": "finish", "payload": summary, "state": state}

    # Not last → go to next question
    state.current_question_index += 1
    next_q = state.questions[state.current_question_index]

    return {
        "action": "ask_question",
        "payload": next_q,
        "state": state
    }
