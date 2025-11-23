# app/main.py
import sys
import os

# Add project root to PYTHONPATH so imports work when running this file directly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.state import InterviewState
from core.controller import handle_user_answer

ASSIGNMENT_PDF_PATH = "/mnt/data/AI Agent Building Assignment - Eightfold.pdf"


def prompt_user(prompt_text: str) -> str:
    try:
        return input(prompt_text)
    except EOFError:
        return ""


def clarify_cli_handler(state: InterviewState, clarify_payload: str):
    """
    Handle the controller 'clarify' action in CLI.

    Returns tuple (action_type, value) where:
      - action_type in {"rephrase", "repeat", "answer_now", "skip"}
      - value: for 'rephrase' the paraphrase string (or None), for 'answer_now' the user's typed answer, else None
    """
    print("\n--- ACTION: clarify ---")
    print(clarify_payload)
    print("\nOptions: [rephrase] [repeat] [answer now] [skip]")
    while True:
        reply = prompt_user("YOU (type option or answer): ").strip()
        if reply == "":
            # treat empty as repeat prompt (ask again)
            return ("repeat", None)

        low = reply.lower().strip()

        # Map common replies to options
        if low in ("rephrase", "r", "re-phrase", "please rephrase", "yes", "y"):
            # Try to extract paraphrase from payload (quoted text) or fallback to last non-empty line
            import re
            paraphrase = None
            m = re.search(r'["“](.+?)["”]', clarify_payload)
            if m:
                paraphrase = m.group(1)
            else:
                lines = [ln.strip() for ln in clarify_payload.splitlines() if ln.strip()]
                if lines:
                    paraphrase = lines[-1]
            return ("rephrase", paraphrase)

        if low in ("repeat", "original", "o", "no", "n"):
            return ("repeat", None)

        if low in ("skip", "s", "i'll pass", "i will pass", "i don't want to answer", "dont want to answer", "pass"):
            return ("skip", None)

        # If the user provided a substantive answer (more than one token or not a known short option),
        # treat it as answering now.
        tokens = reply.split()
        if len(tokens) > 1 or (len(tokens) == 1 and tokens[0].isalpha() and tokens[0].lower() not in
                               {"yes", "y", "no", "n", "ok", "okay", "sure", "hi", "hey"}):
            return ("answer_now", reply)

        # else prompt user to pick a valid option
        print("Please choose one option: rephrase / repeat / answer now / skip — or type your answer directly.")


def run_cli_demo():
    print("=== Interview Agent CLI Demo ===")
    print("Role: software_engineer")
    print("Type 'exit' to quit any time.\n")

    # sample questions (you may already manage these elsewhere)
    questions = [
        "Tell me about a project you are proud of.",
        "How do you debug a production issue?",
        "Explain a data structure you use often.",
    ]

    state = InterviewState(role="software_engineer", questions=questions)
    state.stage = "in_progress"

    # Ask first question
    print(f"INTERVIEWER: {state.questions[state.current_question_index]}")

    while state.stage == "in_progress":
        user_input = prompt_user("YOU: ").strip()
        if not user_input:
            print("(Please type an answer, or 'exit' to quit.)")
            continue
        if user_input.lower() in ("exit", "quit"):
            print("Exiting demo.")
            break

        # Call controller to handle the answer
        result = handle_user_answer(state, user_input)

        # controller returns dict with action and payload
        action = result.get("action")
        payload = result.get("payload")

        # Debug print
        print(f"\n--- ACTION: {action} ---")

        if action == "ask_follow_up":
            print("INTERVIEWER (follow-up):", payload)
            # continue loop to accept the follow-up answer

        elif action == "ask_question":
            print("INTERVIEWER (next question):", payload)
            # continue loop, next input will be treated as answer to next question

        elif action == "clarify":
            # Special flow to handle clarify options in CLI
            choice, value = clarify_cli_handler(state, payload)

            if choice == "rephrase":
                paraphrase = value or "(rephrased question)"
                print("\n--- ACTION: rephrase ---")
                print("INTERVIEWER (rephrased):", paraphrase)
                # Candidate answers rephrased question
                ans = prompt_user("YOU: ").strip()
                if ans.lower() in ("exit", "quit"):
                    print("Exiting demo.")
                    break
                # Treat this as the answer to same question
                result = handle_user_answer(state, ans)
                # Process immediate outcome of this new call
                action = result.get("action")
                payload = result.get("payload")
                if action == "ask_question":
                    print("\n--- ACTION: ask_question ---")
                    print("INTERVIEWER (next question):", payload)
                elif action == "ask_follow_up":
                    print("\n--- ACTION: ask_follow_up ---")
                    print("INTERVIEWER (follow-up):", payload)
                elif action == "clarify":
                    # If controller asks to clarify again, loop back to clarify handler
                    choice2, value2 = clarify_cli_handler(state, payload)
                    # Handle a basic subset of choices for brevity
                    if choice2 == "rephrase":
                        print("Rephrase selected again; re-asking paraphrase.")
                    elif choice2 == "repeat":
                        print("Repeating original question.")
                        print("INTERVIEWER (repeat):", state.questions[state.current_question_index])
                elif action == "finish":
                    print("\n--- ACTION: finish ---")
                    if isinstance(payload, dict):
                        if payload.get("json"):
                            import json
                            print("Final JSON summary:")
                            print(json.dumps(payload["json"], indent=2))
                        if payload.get("text"):
                            print("\nNarrative:\n", payload["text"])
                    else:
                        print(payload)
                    break
                # continue main loop
                continue

            elif choice == "repeat":
                print("\n--- ACTION: repeat original question ---")
                print("INTERVIEWER (repeat):", state.questions[state.current_question_index])
                # next user input will be considered as the answer
                continue

            elif choice == "skip":
                print("\n--- ACTION: skip question ---")
                # Simulate explicit refusal to trigger controller's skip logic
                result = handle_user_answer(state, "I don't want to answer")
                action = result.get("action")
                payload = result.get("payload")
                if action == "ask_question":
                    print("INTERVIEWER (next question):", payload)
                elif action == "finish":
                    print("\n--- ACTION: finish ---")
                    if isinstance(payload, dict):
                        if payload.get("json"):
                            import json
                            print("Final JSON summary:")
                            print(json.dumps(payload["json"], indent=2))
                        if payload.get("text"):
                            print("\nNarrative:\n", payload["text"])
                    else:
                        print(payload)
                    break
                continue

            elif choice == "answer_now":
                # value contains the typed answer
                ans = value
                result = handle_user_answer(state, ans)
                action = result.get("action")
                payload = result.get("payload")
                if action == "ask_question":
                    print("\n--- ACTION: ask_question ---")
                    print("INTERVIEWER (next question):", payload)
                elif action == "ask_follow_up":
                    print("\n--- ACTION: ask_follow_up ---")
                    print("INTERVIEWER (follow-up):", payload)
                elif action == "finish":
                    print("\n--- ACTION: finish ---")
                    if isinstance(payload, dict):
                        if payload.get("json"):
                            import json
                            print("Final JSON summary:")
                            print(json.dumps(payload["json"], indent=2))
                        if payload.get("text"):
                            print("\nNarrative:\n", payload["text"])
                    else:
                        print(payload)
                    break
                continue

        elif action == "finish":
            print("\n=== Interview Finished ===")
            if isinstance(payload, dict):
                if payload.get("json"):
                    import json
                    print("Final JSON summary:")
                    print(json.dumps(payload["json"], indent=2))
                if payload.get("text"):
                    print("\nNarrative:\n", payload["text"])
            else:
                print(payload)
            # Print debug evaluations
            print("\n=== FINAL EVALUATIONS ===")
            from pprint import pprint
            pprint(state.evaluations)
            break

        else:
            # fallback: print payload
            print(payload)

    print("\nDemo complete. Assignment PDF path:")
    print(ASSIGNMENT_PDF_PATH)


if __name__ == "__main__":
    run_cli_demo()
