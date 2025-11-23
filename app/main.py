import sys
import os

# Add project root to PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# app/main.py
from core.state import InterviewState
from llm.llm_providers import generate_response
from core.state import InterviewState
from core.controller import handle_user_answer

def run_cli_demo():
    # sample questions (you likely have these in core/questions.py)
    questions = [
        "Tell me about a project you are proud of.",
        "How do you debug a production issue?",
        "Explain a data structure you use often.",
    ]
    state = InterviewState(role="software_engineer", questions=questions)
    state.stage = "in_progress"
    print("=== Interview Agent CLI Demo ===")
    print("Role:", state.role)
    print("Type 'exit' to quit any time.\n")
    # ask first question
    current_q = state.questions[state.current_question_index]
    print("INTERVIEWER:", current_q)

    while state.stage == "in_progress":
        user_answer = input("YOU: ").strip()
        if not user_answer:
            print("(Please type an answer, or 'exit' to quit.)")
            continue
        if user_answer.lower() in ("exit", "quit"):
            print("Exiting demo.")
            break

        # call controller to handle the answer
        result = handle_user_answer(state, user_answer)

        # controller returns dict with action and payload
        action = result.get("action")
        payload = result.get("payload")

        # debug prints (you'll also see them from inside controller if present)
        print("\n--- ACTION:", action, "---")
        # show payload in readable form
        if action == "ask_follow_up":
            print("INTERVIEWER (follow-up):", payload)
        elif action == "ask_question":
            print("INTERVIEWER (next question):", payload)
        elif action == "finish":
            print("=== Interview Finished ===")
            # payload may contain JSON summary or text
            if isinstance(payload, dict):
                print("SUMMARY JSON:", payload.get("json"))
                if payload.get("text"):
                    print("SUMMARY TEXT:", payload.get("text"))
            else:
                print(payload)
            # print final evaluations for debug
            print("\n=== FINAL EVALUATIONS ===")
            from pprint import pprint
            pprint(state.evaluations)
            break
        else:
            # fallback: print payload
            print(payload)

        # if the controller returned ask_question or ask_follow_up the state should already be updated
        # print the question the user should answer next (controller may already have included it)
        if action in ("ask_follow_up", "ask_question"):
            # the payload is the question string; just loop continues and will read user's next input
            pass

    print("\nDemo complete. Assignment PDF path:")
    print("/mnt/data/AI Agent Building Assignment - Eightfold.pdf")

if __name__ == "__main__":
    run_cli_demo()
