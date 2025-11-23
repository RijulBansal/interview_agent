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
    st.session_state.state.stage = "in_progress"
    st.session_state.transcript = []  # store Q/A interactions

state = st.session_state.state

#st.title("Interview Agent — Eightfold AI Assignment Demo")
#st.caption("Built using your custom agentic interview pipeline.")

# >>> ADDED: keep current answer text & spoken questions in session
if "answer_text" not in st.session_state:
    st.session_state.answer_text = ""

if "spoken_questions" not in st.session_state:
    # maps question_text -> audio bytes
    st.session_state.spoken_questions = {}

# --- Retrieve Current Prompt (Question / Follow-up) ---
# --- Retrieve Current Prompt (Question / Follow-up) ---
if state.pending_followup:
    current_prompt = state.pending_followup
    st.info(f"Follow-up Question: {current_prompt}")
else:
    current_prompt = state.questions[state.current_question_index]
    st.info(f"Main Question {state.current_question_index + 1}: {current_prompt}")

# >>> ADDED: Text-to-Speech for the agent (read the question/follow-up)
if current_prompt not in st.session_state.spoken_questions:
    with st.spinner("Generating audio for question..."):
        try:
            audio_bytes = tts_question(current_prompt)
            st.session_state.spoken_questions[current_prompt] = audio_bytes
        except Exception as e:
            st.warning(f"Could not generate audio for question: {e}")

audio_bytes = st.session_state.spoken_questions.get(current_prompt)
if audio_bytes:
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

# >>> ADDED: voice recording using mic_recorder
audio_data = mic_recorder(
    start_prompt="🎤 Start recording",
    stop_prompt="⏹ Stop",
    key="mic_recorder",
)

# When we have recorded audio, let user transcribe it into the text box
if audio_data is not None:
    if st.button("Transcribe Recording"):
        try:
            from io import BytesIO
            audio_file = BytesIO(audio_data["bytes"])
            audio_file.name = "answer.wav"

            with st.spinner("Transcribing your answer..."):
                transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                )

            # Put recognized text into the textbox for confirmation/editing
            st.session_state.answer_text = transcript.text
            st.rerun()
        except Exception as e:
            st.warning(f"Transcription failed: {e}")


col1, col2, col3, col4 = st.columns(4)

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
        new_q = generate_rephrase_with_llm(current_prompt, state.role)
        st.info(f"Rephrased Version:\n\n**{new_q}**")

# --- Repeat Question ---
with col3:
    if st.button("Repeat"):
        st.session_state.transcript.append({"question_repeat": current_prompt})
        st.rerun()

# --- Skip Question ---
with col4:
    if st.button("Skip"):
        result = handle_user_answer(state, "I don't want to answer")
        st.session_state.transcript.append(
            {"question": current_prompt, "answer": "(skipped)", "result": result}
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
