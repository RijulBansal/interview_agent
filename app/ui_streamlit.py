# app/ui_streamlit.py
import sys
import os

# Resolve project root directory dynamically
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

import streamlit as st
import json
from core.state import InterviewState
from core.controller import handle_user_answer
from core.report import export_pdf
from openai import OpenAI
client = OpenAI()  
from streamlit_mic_recorder import mic_recorder
from io import BytesIO  # >>> ADDED
import base64
import streamlit.components.v1 as components
from core.final_summary import generate_final_feedback_with_llm
from core.question_generator import generate_question_list



# --- Demo question scripts for testing audio and other ui components ---

def get_demo_questions(role: str, mode: str):
    # normalise
    role = (role or "").lower()
    mode = (mode or "").lower()

    # SALES ROLE (normal)
    if role == "sales_associate":
        return [
            "Tell me about a time you successfully convinced a hesitant customer to make a purchase.",
            "How do you typically handle customer objections?",
            "Can you give an example of turning a frustrated customer into a satisfied one?",
        ]

    # SOFTWARE ENGINEER — BRIEF MODE
    if role == "software_engineer" and mode == "brief":
        return [
    "Tell me about a Python project you’re proud of.",
    "What improvement did you implement that made the model faster?",
    "Explain OOP in C++.",
    "Can you give a real example from your own code?",
    "How do you approach debugging a segmentation fault?",
    "Did you debug similar issues in that project?",
]


    # SOFTWARE ENGINEER — NORMAL MODE
    if role == "software_engineer" and mode == "normal":
        return [
            "Tell me about a Python project you’re proud of.",
            "Explain polymorphism in OOP with an example from your own code.",
            "How do you approach debugging a segmentation fault in C++?",
        ]

    # SOFTWARE ENGINEER — IN-DEPTH / TOUGH MODE
    if role == "software_engineer" and mode in ("deep", "tough", "in-depth"):
        return [
    "Tell me about the architecture of a Python project you recently worked on.",
    "What bottleneck did you encounter during parsing?",
    "How did you address that contention?",
    "Compare unique_ptr and shared_ptr.",
    "When would you avoid shared_ptr due to overhead?",
    "How does that analogy help explain reference counting?",
    "Walk me through how you’d solve ‘find cycle in a directed graph.’",
    "Can you outline the steps precisely?",
    "Can you give a small real example?",
    "How would you apply OOP principles consistently across both Python and C++ in the same project?",
    "How would polymorphism differ between the two?",
    "Which approach did you personally find easier when debugging?",
    "How would you debug intermittent crashes in such a system?",
    "What exact bug did ASAN help you catch last time?",
]


    # fallback default (if something unexpected)
    return [
        "Tell me about a project you are proud of.",
        "How do you debug a production issue?",
        "Explain a data structure you use often.",
    ]

# --- Real question bank based on role + mode + skills ---

def get_questions_for(role: str, mode: str, skills: list[str]) -> list[str]:
    role = (role or "").lower()
    mode = (mode or "").lower()
    skills = [s.lower() for s in (skills or [])]

    # Helper to make a short skills string
    skills_str = ", ".join(skills) if skills else "your core skills"

    # SOFTWARE ENGINEER
    if role == "software_engineer":
        questions = []

        # Always start with a project question tailored to skills
        questions.append(
            f"Tell me about a project you are proud of that used {skills_str}."
        )

        if mode == "brief":
            questions.append("What data structure do you use most often and why?")
            questions.append("Explain polymorphism in OOP in simple terms.")

        elif mode == "normal":
            questions.extend([
                "Explain polymorphism in OOP with an example from your own code.",
                "How do you approach debugging a segmentation fault in C++?",
                "Describe a time when you optimized Python code for performance.",
            ])

        else:  # "deep" / in-depth
            questions.extend([
                "Walk me through how you would detect a cycle in a directed graph.",
                "Compare unique_ptr and shared_ptr in C++ and explain when you would avoid shared_ptr.",
                "How would you apply OOP principles consistently across both Python and C++ in the same project?",
            ])

        return questions

    # SALES ASSOCIATE
    if role == "sales_associate":
        if mode == "brief":
            return [
                "Tell me about a time you successfully convinced a hesitant customer to make a purchase.",
                "How do you typically handle customer objections?",
            ]
        elif mode == "normal":
            return [
                "Tell me about a time you successfully convinced a hesitant customer to make a purchase.",
                "Can you give an example of turning a frustrated customer into a satisfied one?",
                "How do you balance hitting sales targets with being honest with customers?",
            ]
        else:  # "deep"
            return [
                "Describe your full sales cycle for a complex, multi-stakeholder deal.",
                "Tell me about a deal you lost. What did you learn and change afterwards?",
            ]

    # CUSTOMER SUPPORT (simple example)
    if role == "customer_support":
        return [
            "Tell me about a time you handled a very frustrated customer.",
            "How do you decide when to escalate an issue to a senior team member?",
        ]

    # fallback default
    return [
        "Tell me about a project you are proud of.",
        "How do you debug a production issue?",
        "Explain a data structure you use often.",
    ]


# >>> ADDED: helper to convert question text to speech (MP3 bytes)
def tts_question(text: str) -> bytes:
    response = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice="alloy",
        input=text,
    )
    return response.read()  # ← THIS FIXES YOUR ERROR


# --- Initialize Session State ---
if "state" not in st.session_state:
    st.session_state.state = InterviewState(
        role="software_engineer",
        questions=[
            "Tell me about a project you are proud of.",
            "How do you debug a production issue?",
            "Explain a data structure you use often."
        ]
    )
    st.session_state.state.stage = "not_started"
    st.session_state.transcript = []  # store Q/A interactions

if "last_audio_hash" not in st.session_state:
    st.session_state.last_audio_hash = None

if "played_questions" not in st.session_state:
    st.session_state.played_questions = []

if "rephrased_questions" not in st.session_state:
    st.session_state.rephrased_questions = {}

if "skills" not in st.session_state:
    st.session_state.skills = []

if "skill_input_text" not in st.session_state:
    st.session_state.skill_input_text = ""



state = st.session_state.state


st.title("Interview Agent - Eightfold AI Assignment Demo")
#st.caption("Built using your custom agentic interview pipeline.")

# --- Interview Mode Selector ---
if "interview_mode" not in st.session_state:
    st.session_state.interview_mode = "normal"  # default

mode_label = st.radio(
    "Interview mode",
    ["Brief (efficient)", "Normal", "In-depth"],
    index=1,
    horizontal=True,
    disabled=(state.stage != "not_started"),
)

mode_map = {
    "Brief (efficient)": "brief",
    "Normal": "normal",
    "In-depth": "deep",
}

selected_mode = mode_map[mode_label]
st.session_state.interview_mode = selected_mode

# keep the current state's mode in sync with the UI selection
state.mode = selected_mode

# --- Role Selector ---
if "role" not in st.session_state:
    st.session_state.role = state.role or "software_engineer"

ROLE_OPTIONS = [
    "Software Engineer",
    "Sales Associate",
    "Customer Support",
    "Other (custom)",
]

role_label = st.selectbox(
    "Select the role for this mock interview:",
    ROLE_OPTIONS,
    disabled=(state.stage != "not_started"),
)

if role_label == "Other (custom)":
    custom_role_value = st.text_input(
        "Enter custom role (e.g., Data Scientist, Product Manager):",
        value=custom_role_value,
        disabled=(state.stage != "not_started"),
    )

    st.session_state.custom_role = custom_role_value.strip()
    # Fallback if user leaves it empty
    selected_role = custom_role_value.strip() or "software_engineer"
else:
    # Map human label -> internal key
    role_map = {
        "Software Engineer": "software_engineer",
        "Sales Associate": "sales_associate",
        "Customer Support": "customer_support",
    }
    selected_role = role_map[role_label]

# Keep both session + state in sync
st.session_state.role = selected_role
state.role = selected_role

# --- Skills to Focus On ---
st.subheader("Skills you want to test")

skills_disabled = (state.stage != "not_started")

row1, row2 = st.columns([3, 1])

with row1:
    skill_input = st.text_input(
       "Add a skill (e.g., DSA, System Design, Communication):",
        value=st.session_state.skill_input_text,
        key="skill_input",
        disabled=skills_disabled,
    )

with row2:
    st.write("")            # one spacer
    st.write("")            # second spacer (adjust if needed)
    add_skill = st.button("Add skill", disabled=skills_disabled)

# Add skill when button clicked
if add_skill and not skills_disabled:
    new_skill = (skill_input or "").strip()
    if new_skill and new_skill not in st.session_state.skills:
        st.session_state.skills.append(new_skill)
    # clear the *separate* value holder, not the widget key
    st.session_state.skill_input_text = ""
    st.rerun()

# Show skills as small removable tags
if st.session_state.skills:
    st.caption("Skills selected:")

    chip_cols = st.columns(min(len(st.session_state.skills), 4) or 1)

    for i, skill in enumerate(st.session_state.skills):
        col = chip_cols[i % len(chip_cols)]
        with col:
            if skills_disabled:
                # When interview already started, show non-clickable chip
                st.markdown(f"""
                    <div style="
                        display: inline-flex;
                        align-items: center;
                        border: 1px solid #444;
                        background-color: #2c2c2c;
                        padding: 2px 8px;
                        border-radius: 8px;
                        margin: 4px 0;
                        font-size: 0.78rem;
                    ">
                        {skill}
                    </div>
                """, unsafe_allow_html=True)

            else:
                # Render the chip as a clickable button (styled as the chip)
                chip_clicked = st.button(
                    skill,
                    key=f"skill_tag_{i}",
                    help=f"Click to remove {skill}",
                )

                # Override Streamlit button styling using HTML injection
                st.markdown(
                    f"""
                    <style>
                    div.stButton > button[kind="secondary"][data-testid="baseButton-secondary"][aria-label="{skill}"] {{
                        display: inline-flex;
                        align-items: center;
                        border: 1px solid #444 !important;
                        background-color: #2c2c2c !important;
                        padding: 2px 8px !important;
                        border-radius: 8px !important;
                        margin: 4px 0 !important;
                        font-size: 0.78rem !important;
                        color: #f5f5f5 !important;
                        height: auto !important;
                    }}
                    </style>
                    """,
                    unsafe_allow_html=True,
                )

                # Remove skill when clicked
                if chip_clicked:
                    st.session_state.skills.remove(skill)
                    st.rerun()

st.markdown("---")

state.skills = list(st.session_state.get("skills", []))

# --- Start Interview Button ---
if state.stage == "not_started":
    if st.button("🚀 Start Interview"):

        # 1. Store role, mode, and skills in backend state
        state.role = st.session_state.get("selected_role", state.role)
        state.mode = selected_mode
        state.skills = list(st.session_state.get("skills", []))

        # 2. Generate question list from LLM
        with st.spinner("Generating interview questions..."):
            state.questions = generate_question_list(
                role=state.role,
                mode=state.mode,
                skills=state.skills,
            )

        # 3. Reset entire interview flow
        state.stage = "in_progress"
        state.current_question_index = 0
        state.answers = []
        state.evaluations = []
        state.pending_followup = None
        state.followup_depth = 0
        state.followup_history = []
        state.topic_escape_count = 0

        # 4. Clear UI fields
        st.session_state.answer_text = ""
        st.session_state.spoken_questions = {}
        st.session_state.played_questions = []
        st.session_state.transcript = []

        # 5. Refresh UI
        st.rerun()


# If interview not started yet, stop here (no questions, no TTS, no answer box)
if state.stage == "not_started":
    st.info("Select role and mode, then click **Start Interview** to begin.")
    st.stop()


# >>> ADDED: keep current answer text & spoken questions in session
if "answer_text" not in st.session_state:
    st.session_state.answer_text = ""

if "spoken_questions" not in st.session_state:
    # maps question_text -> audio bytes
    st.session_state.spoken_questions = {}

# --- Retrieve Current Prompt (Question / Follow-up) ---
if state.pending_followup:
    # For follow-ups we always show the exact follow-up text
    current_prompt = state.pending_followup
    st.info(f"Follow-up Question: {current_prompt}")
else:
    # For main questions, allow a rephrased version to override the display text
    q_idx = state.current_question_index
    base_q = state.questions[q_idx]
    rephrased_map = st.session_state.get("rephrased_questions", {})
    current_prompt = rephrased_map.get(q_idx, base_q)
    st.info(f"Main Question {q_idx + 1}: {current_prompt}")


# >>> ADDED: Text-to-Speech for the agent (read the question/follow-up)
if current_prompt not in st.session_state.spoken_questions:
    with st.spinner("Generating audio for question..."):
        try:
            audio_bytes = tts_question(current_prompt)
            st.session_state.spoken_questions[current_prompt] = audio_bytes
        except Exception as e:
            st.warning(f"Could not generate audio for question: {e}")

audio_bytes = st.session_state.spoken_questions.get(current_prompt)

# --- Auto-play on first time, keep player for replay ---
if "played_questions" not in st.session_state:
    # store as list so it's JSON-serializable
    st.session_state.played_questions = []

if audio_bytes:
    # auto-play the first time this question appears
    if current_prompt not in st.session_state.played_questions:
        b64 = base64.b64encode(audio_bytes).decode()
        components.html(
            f"""
            <audio autoplay>
                <source src="data:audio/mp3;base64,{b64}" type="audio/mpeg">
            </audio>
            """,
            height=0,
            width=0,
        )
        st.session_state.played_questions.append(current_prompt)

    # normal Streamlit audio player so user can replay the question
    st.audio(audio_bytes, format="audio/mp3")


# --- User Answer Box ---
# --- User Answer Box (text + voice) ---
st.write("### Your Answer")

# bind text area to session_state.answer_text via value (not key)
answer = st.text_area(
    "You can type your answer or use voice input below:",
    height=160,
    value=st.session_state.answer_text,
)

st.write("Or record your answer with your voice:")

# --- Voice Input Section (mic recorder) ---
audio_data = mic_recorder(
    start_prompt="🎤 Start recording",
    stop_prompt="⏹ Stop",
    key="mic_recorder",
)

# --- Auto-transcribe as soon as recording stops ---
if audio_data is not None and "bytes" in audio_data:
    import hashlib
    from io import BytesIO

    audio_bytes = audio_data["bytes"]

    # Create hash to avoid re-transcribing the same audio after every rerun
    current_hash = hashlib.md5(audio_bytes).hexdigest()

    if current_hash != st.session_state.last_audio_hash:
        st.session_state.last_audio_hash = current_hash

        audio_file = BytesIO(audio_bytes)
        audio_file.name = "answer.wav"

        try:
            with st.spinner("Transcribing your answer..."):
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="en",
                )

            # Put text directly into the answer text area
            st.session_state.answer_text = transcript.text

            # Rerun the app so the text area instantly updates
            st.rerun()

        except Exception as e:
            st.warning(f"Transcription failed: {e}")


col1, col2, col3, col4, col5 = st.columns(5)

# --- Submit Answer ---
with col1:
    if st.button("Submit"):
        cleaned = (answer or "").strip()
        if cleaned == "":
            st.warning("Please provide an answer (typed or via voice) before submitting.")
        else:
            result = handle_user_answer(state, cleaned)
            st.session_state.transcript.append(
                {"question": current_prompt, "answer": cleaned, "result": result}
            )
            # clear the box for the next question
            st.session_state.answer_text = ""
            st.rerun()



# --- Rephrase Current Question ---

with col2:
    if st.button("Rephrase"):
        from core.followup import generate_rephrase_with_llm

        # Decide what to rephrase: follow-up or main question
        if state.pending_followup:
            base_q = state.pending_followup
        else:
            base_q = state.questions[state.current_question_index]

        new_q = generate_rephrase_with_llm(base_q, state.role)

        # If this is a main question: store the rephrased version for this index
        if not state.pending_followup:
            st.session_state.rephrased_questions[state.current_question_index] = new_q
        else:
            # If we rephrased a follow-up, update the pending_followup text
            state.pending_followup = new_q

        # Ensure TTS will treat this as a fresh question to speak once
        if "spoken_questions" in st.session_state:
            st.session_state.spoken_questions.pop(new_q, None)
        if "played_questions" in st.session_state and new_q in st.session_state.played_questions:
            st.session_state.played_questions.remove(new_q)

        # Rerun so the rephrased question becomes the displayed current_prompt
        st.rerun()



# --- Repeat Question ---
with col3:
    if st.button("Repeat"):
        # Log that the question was repeated (optional, for transcript)
        st.session_state.transcript.append({"question_repeat": current_prompt})

        # Force the TTS to auto-play again for this prompt on next rerun
        if "played_questions" in st.session_state and current_prompt in st.session_state.played_questions:
            st.session_state.played_questions.remove(current_prompt)

        st.rerun()


# --- Skip Question ---
with col4:
    if st.button("Skip"):
        result = handle_user_answer(state, "I don't want to answer")
        st.session_state.transcript.append(
            {"question": current_prompt, "answer": "(skipped)", "result": result}
        )
        st.rerun()

# --- End Interview Early ---
with col5:
    if state.stage == "in_progress" and st.button("End Interview"):
        # Mark finished and generate summary based on current answers/evaluations
        state.stage = "finished"
        summary = generate_final_feedback_with_llm(
            state.role, state.questions, state.answers, state.evaluations, state.skills,
        )

        # Create a synthetic "finish" result so the existing finished-block works
        finish_result = {
            "action": "finish",
            "payload": summary,
            "state": state,
        }

        st.session_state.transcript.append(
            {
                "question": "(Interview ended early by user)",
                "answer": "",
                "result": finish_result,
            }
        )
        st.rerun()

# --- If Interview Finished: Show Summary ---
if state.stage == "finished":
    st.success("Interview Completed.")

    # Last result in transcript should be the "finish" action
    final_result = st.session_state.transcript[-1]["result"]
    raw_summary = final_result["payload"]  # this is {"json": j, "text": text} from generate_final_feedback_with_llm

    # ---- Unwrap final summary JSON ----
    final_summary = raw_summary
    if isinstance(raw_summary, dict) and isinstance(raw_summary.get("json"), dict):
        inner = raw_summary["json"].copy()  # copy the inner JSON

        # Optionally preserve any extra free-text from the LLM
        extra_text = raw_summary.get("text")
        if extra_text:
            inner.setdefault("raw_text", extra_text)

        final_summary = inner

    # (Optional) store unwrapped summary in session_state for later use
    st.session_state.final_summary = final_summary

    st.subheader("Download Full PDF Report")

    # This will now show a dict like:
    # {
    #   "overall_scores": {...},
    #   "strengths": [...],
    #   "weaknesses": [...],
    #   "top_tips": [...],
    #   "summary": "...",
    #   "raw_text": "..."  # optional
    # }
    st.json(final_summary)

    # ---- PDF EXPORT BUTTON ----
    if st.button("Download PDF Report"):
        pdf_path = export_pdf(
            transcript=st.session_state.transcript,
            final_summary=final_summary,
            role=state.role,
            filename="interview_report.pdf"
        )

        with open(pdf_path, "rb") as f:
            st.download_button(
                label="Click to Download PDF",
                data=f,
                file_name="interview_report.pdf",
                mime="application/pdf"
            )

    st.stop()


# --- Show Transcript ---
st.subheader("Conversation Transcript")
for item in st.session_state.transcript:
    if "question" in item:
        st.markdown(f"**Q:** {item['question']}")
        st.markdown(f"**A:** {item['answer']}")
        st.markdown(f"*Action:* {item['result']['action']}")
    else:
        st.markdown(f"**(Repeated)** {item['question_repeat']}")
