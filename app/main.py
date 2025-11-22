# app/main.py
from core.state import InterviewState
from llm.llm_providers import generate_response

def run_demo():
    # easiest: run a linear flow to test LLM connectivity
    state = InterviewState(role="software_engineer", questions=[
        "Tell me about a project you are proud of.",
        "How do you debug a production issue?",
        "Explain a data structure you use often."
    ])
    state.stage = "in_progress"
    for q in state.questions:
        print("INTERVIEWER:", q)
        ans = input("YOU: ")
        state.answers.append(ans)
    print("Interview finished. Generating summary...")
    prompt = [{"role":"system","content":"You are an interview coach."},
              {"role":"user","content": f"Questions: {state.questions}\nAnswers: {state.answers}\nGenerate strengths and improvements."}]
    out = generate_response(prompt)
    print("FEEDBACK:", out)

if __name__ == "__main__":
    run_demo()
