# core/report.py

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
import matplotlib.pyplot as plt
import os
from datetime import datetime
import math
import numpy as np


styles = getSampleStyleSheet()
title_style = ParagraphStyle(
    'TitleStyle',
    parent=styles['Heading1'],
    fontSize=22,
    alignment=TA_CENTER,
    spaceAfter=20
)
section_style = ParagraphStyle(
    'SectionStyle',
    parent=styles['Heading2'],
    fontSize=16,
    alignment=TA_LEFT,
    spaceBefore=14,
    spaceAfter=8
)
normal_style = styles["BodyText"]


# ---- NEW: Create bar chart of evaluation scores ----
def create_scores_chart(scores_dict, out_path="scores_chart.png"):
    labels = list(scores_dict.keys())
    values = list(scores_dict.values())

    plt.figure(figsize=(6, 3))
    plt.bar(labels, values)
    plt.title("Evaluation Scores")
    # if score values are >5 (rare), normalize; but generally assume 0-5 scale
    plt.ylim(0, 5)
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()
    return out_path


def compute_overall_rating(scores):
    """
    Weighted calculation to give a single interview score (0-100).
    Expect scores in 0-5 range.
    """
    weights = {
        "clarity": 0.25,
        "structure": 0.25,
        "technical_depth": 0.30,
        "relevance": 0.20
    }
    rating = 0.0
    for key, weight in weights.items():
        rating += scores.get(key, 0) * weight
    # convert 0-5 -> 0-100
    rating = (rating / 5.0) * 100.0
    return round(rating, 2)

def _infer_scores_from_transcript(transcript):
    """
    Walk the transcript (list of dicts with 'result' or evaluation payloads) and average
    any found per-answer scores. Returns dict of scores or None.
    """
    keys = ["clarity", "structure", "technical_depth", "relevance"]
    accum = {k: 0.0 for k in keys}
    count = 0

    for item in transcript:
        # item structure in your UI: {"question":..., "answer":..., "result": result_dict}
        res = item.get("result")
        if not isinstance(res, dict):
            continue

        # result may be {"action":..., "payload": {...}}
        payload = res.get("payload")
        # payload might be the full final_summary (when finish), or evaluation dict
        eval_dict = None

        if isinstance(payload, dict):
            # if it contains overall_scores directly
            if "overall_scores" in payload and isinstance(payload["overall_scores"], dict):
                eval_dict = payload["overall_scores"]
            # if payload itself contains the flat metrics
            elif all(k in payload for k in keys):
                eval_dict = {k: payload[k] for k in keys}
        # sometimes evaluator stored metrics directly under res (less likely)
        elif all(k in res for k in keys):
            eval_dict = {k: res[k] for k in keys}

        if eval_dict:
            found_any = False
            for k in keys:
                v = eval_dict.get(k)
                if v is None:
                    continue
                try:
                    accum[k] += float(v)
                    found_any = True
                except Exception:
                    pass
            if found_any:
                count += 1

    if count > 0:
        return {k: round(accum[k] / count, 2) for k in keys}
    return None

def compute_answer_ratio(transcript):
    """
    Compute fraction of main questions that were actually answered (not refused/skipped).
    Returns (ratio, answered_count, total_count, refused_any).
    """
    total = 0
    answered = 0
    refused_any = False

    # Try to get the final InterviewState from the last transcript entry
    state = None
    if transcript:
        last = transcript[-1]
        res = last.get("result", {})
        if isinstance(res, dict):
            state = res.get("state")

    if state is not None and getattr(state, "questions", None) is not None:
        # Use canonical main questions and evaluation flags
        questions = getattr(state, "questions", [])
        evaluations = list(getattr(state, "evaluations", []))
        total = len(questions)

        for idx in range(total):
            ev = evaluations[idx] if idx < len(evaluations) else {}

            skipped_flag = bool(
                ev.get("skipped")
                or ev.get("skipped_due_to_refusal")
                or ev.get("skipped_due_to_unrelated_replies")
            )

            if ev.get("knowledge_intent", "").lower() in ("refuse", "unknown"):
                skipped_flag = True

            if skipped_flag:
                refused_any = True
                continue

            answered += 1
    else:
        # Fallback: derive from transcript answers only
        questions = [item for item in transcript if "question" in item]
        total = len(questions)
        for item in questions:
            ans = (item.get("answer") or "").strip().lower()
            if ans in (
                "",
                "(skipped)",
                "i don't want to answer",
                "i dont want to answer",
                "i dont answer",
                "i cannot answer",
            ):
                refused_any = True
                continue
            answered += 1

    if total <= 0:
        # No questions → no penalty
        return 1.0, 0, 0, refused_any

    ratio = answered / total
    return ratio, answered, total, refused_any

def create_scores_radar_chart(scores, filename="scores_radar_chart.png"):
    """
    Radar / spider chart for the overall scores.

    Expected scores keys: clarity, structure, technical_depth, relevance
    Original scale: 0–4  (we'll show them as 0–100 on the radial axis for a smoother look)
    """
    labels = ["Clarity", "Structure", "Technical Depth", "Relevance"]

    # Get values on 0–4 scale
    vals_0_4 = [
        float(scores.get("clarity", 0.0)),
        float(scores.get("structure", 0.0)),
        float(scores.get("technical_depth", 0.0)),
        float(scores.get("relevance", 0.0)),
    ]

    # Optional: scale up to 0–100 for nicer circular grid
    vals = [v * 25.0 for v in vals_0_4]   # 4 -> 100
    num_vars = len(labels)

    # Angles for each axis (equally spaced), rotated so first label is at the top
    angles = np.linspace(0, 2 * math.pi, num_vars, endpoint=False)
    angles = angles + math.pi / 2.0      # rotate 90° so first axis is at the top
    angles = angles.tolist()

    # Close the loop
    angles += angles[:1]
    vals += vals[:1]

    # Make the plot square so the circle is really a circle
    fig, ax = plt.subplots(subplot_kw=dict(polar=True), figsize=(4, 4))

    # Plot + fill
    ax.plot(angles, vals, linewidth=2)
    ax.fill(angles, vals, alpha=0.25)

    # Category labels
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels)

    # Radial limits and grid: 0–100 with nice concentric rings
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(["20", "40", "60", "80", "100"])
    ax.set_rlabel_position(45)  # move radial labels away from axes

    # Make grid visible and layout tight
    ax.grid(True)
    fig.tight_layout()
    fig.savefig(filename, bbox_inches="tight", dpi=150)
    plt.close(fig)

    return filename


'''def export_pdf(transcript, final_summary, filename="interview_report.pdf"):
    """
    transcript: list of {"question", "answer", "result"}
    final_summary: dict returned by controller finish payload; may or may not include overall_scores
    """
    # Try to obtain scores robustly
    scores = None
    if isinstance(final_summary, dict):
        # primary: overall_scores key
        scores = final_summary.get("overall_scores")
        if isinstance(scores, dict):
            # ensure numeric values
            for k in ["clarity", "structure", "technical_depth", "relevance"]:
                scores[k] = float(scores.get(k, 0.0))
        else:
            # secondary: flat keys in final_summary
            candidates = {}
            for k in ["clarity", "structure", "technical_depth", "relevance"]:
                if k in final_summary:
                    try:
                        candidates[k] = float(final_summary[k])
                    except Exception:
                        pass
            if candidates:
                # fill missing keys with 0
                for k in ["clarity", "structure", "technical_depth", "relevance"]:
                    candidates.setdefault(k, 0.0)
                scores = candidates

    # tertiary: infer from transcript evaluations
    if not isinstance(scores, dict):
        inferred = _infer_scores_from_transcript(transcript)
        if inferred:
            scores = inferred

    # final fallback: neutral mid-range scores (3/5)
    if not isinstance(scores, dict):
        scores = {"clarity": 3.0, "structure": 3.0, "technical_depth": 3.0, "relevance": 3.0}

    # Build document
    doc = SimpleDocTemplate(filename, pagesize=letter)
    story = []

    # Title page
    story.append(Paragraph("Interview Report", title_style))
    story.append(Paragraph(datetime.now().strftime("%B %d, %Y"), normal_style))
    story.append(Spacer(1, 40))
    story.append(Paragraph("Role: Software Engineer", section_style))
    story.append(Spacer(1, 20))
    story.append(PageBreak())

    # Transcript
    story.append(Paragraph("Conversation Transcript", section_style))
    story.append(Spacer(1, 12))
    for i, item in enumerate(transcript, start=1):
        if "question" in item:
            story.append(Paragraph(f"<b>Q{i}: {item['question']}</b>", normal_style))
            story.append(Paragraph(f"A: {item['answer']}", normal_style))
            # print action if available
            act = item.get("result", {}).get("action")
            if act:
                story.append(Paragraph(f"<i>Action: {act}</i>", normal_style))
            story.append(Spacer(1, 12))
        elif "question_repeat" in item:
            story.append(Paragraph(f"<b>(Repeated)</b> {item['question_repeat']}", normal_style))
            story.append(Spacer(1, 12))

    story.append(PageBreak())

    # Score chart + overall rating
    chart_path = create_scores_chart(scores)
    overall_rating = compute_overall_rating(scores)

    story.append(Paragraph("Scoring Overview", section_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"<b>Overall Rating:</b> {overall_rating} / 100", normal_style))
    story.append(Spacer(1, 20))
    story.append(Image(chart_path, width=400, height=200))
    story.append(Spacer(1, 30))
    story.append(PageBreak())

    # Final summary (if any)
    story.append(Paragraph("Final Evaluation Summary", section_style))
    if isinstance(final_summary, dict):
        if final_summary.get("summary"):
            story.append(Paragraph(f"<b>Overall Summary:</b><br/>{final_summary['summary']}", normal_style))
            story.append(Spacer(1, 16))

        if final_summary.get("strengths"):
            story.append(Paragraph("<b>Strengths:</b>", normal_style))
            for s in final_summary["strengths"]:
                story.append(Paragraph(f"- {s}", normal_style))
            story.append(Spacer(1, 12))

        if final_summary.get("weaknesses"):
            story.append(Paragraph("<b>Weaknesses:</b>", normal_style))
            for w in final_summary["weaknesses"]:
                story.append(Paragraph(f"- {w}", normal_style))
            story.append(Spacer(1, 12))

        if final_summary.get("top_tips"):
            story.append(Paragraph("<b>Top Tips:</b>", normal_style))
            for t in final_summary["top_tips"]:
                story.append(Paragraph(f"- {t}", normal_style))
            story.append(Spacer(1, 12))

    doc.build(story)
    return filename
'''
#Modified criteria for evaluation
def export_pdf(transcript, final_summary, filename="interview_report.pdf"):
    """
    transcript: list of {"question", "answer", "result"}
    final_summary: dict returned by controller finish payload; may or may not include overall_scores
    """
    # Try to obtain scores robustly
    scores = None
    if isinstance(final_summary, dict):
        # primary: overall_scores key
        scores = final_summary.get("overall_scores")
        if isinstance(scores, dict):
            # ensure numeric values
            for k in ["clarity", "structure", "technical_depth", "relevance"]:
                scores[k] = float(scores.get(k, 0.0))
        else:
            # secondary: flat keys in final_summary
            candidates = {}
            for k in ["clarity", "structure", "technical_depth", "relevance"]:
                if k in final_summary:
                    try:
                        candidates[k] = float(final_summary[k])
                    except Exception:
                        pass
            if candidates:
                # fill missing keys with 0
                for k in ["clarity", "structure", "technical_depth", "relevance"]:
                    candidates.setdefault(k, 0.0)
                scores = candidates

    # tertiary: infer from transcript evaluations
    if not isinstance(scores, dict):
        inferred = _infer_scores_from_transcript(transcript)
        if inferred:
            scores = inferred

    # final fallback: neutral mid-range scores (3/5)
    if not isinstance(scores, dict):
        scores = {"clarity": 3.0, "structure": 3.0, "technical_depth": 3.0, "relevance": 3.0}

    # --- NEW: compute answer_ratio based on how many main questions were actually answered ---
    answer_ratio, answered_count, total_count, refused_any = compute_answer_ratio(transcript)

    # Build document
    doc = SimpleDocTemplate(filename, pagesize=letter)
    story = []

    # Title page
    story.append(Paragraph("Interview Report", title_style))
    story.append(Paragraph(datetime.now().strftime("%B %d, %Y"), normal_style))
    story.append(Spacer(1, 40))
    story.append(Paragraph("Role: Software Engineer", section_style))
    story.append(Spacer(1, 20))
    story.append(PageBreak())

    # Transcript
    story.append(Paragraph("Conversation Transcript", section_style))
    story.append(Spacer(1, 12))
    for i, item in enumerate(transcript, start=1):
        if "question" in item:
            story.append(Paragraph(f"<b>Q{i}: {item['question']}</b>", normal_style))
            story.append(Paragraph(f"A: {item['answer']}", normal_style))
            # print action if available
            act = item.get("result", {}).get("action")
            if act:
                story.append(Paragraph(f"<i>Action: {act}</i>", normal_style))
            story.append(Spacer(1, 12))
        elif "question_repeat" in item:
            story.append(Paragraph(f"<b>(Repeated)</b> {item['question_repeat']}", normal_style))
            story.append(Spacer(1, 12))

    story.append(PageBreak())

    # Score chart + overall rating
    chart_path = create_scores_chart(scores)
    radar_chart_path = create_scores_radar_chart(scores)

    raw_overall_rating = compute_overall_rating(scores)
    adjusted_overall_rating = round(raw_overall_rating * answer_ratio, 2)

    story.append(Paragraph("Scoring Overview", section_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"<b>Overall Rating:</b> {adjusted_overall_rating} / 100", normal_style))
    story.append(Spacer(1, 20))

    # Bar chart for scores
    story.append(Image(chart_path, width=400, height=200))
    story.append(Spacer(1, 20))

    # NEW: Radar / spider chart
    story.append(Paragraph("Skill Profile (Radar Chart)", normal_style))
    story.append(Spacer(1, 8))
    story.append(Image(radar_chart_path, width=300, height=300))
    story.append(Spacer(1, 30))

    story.append(PageBreak())

    # Final summary (if any)
    story.append(Paragraph("Final Evaluation Summary", section_style))
    if isinstance(final_summary, dict):
        if final_summary.get("summary"):
            story.append(Paragraph(f"<b>Overall Summary:</b><br/>{final_summary['summary']}", normal_style))
            story.append(Spacer(1, 16))

        if final_summary.get("strengths"):
            story.append(Paragraph("<b>Strengths:</b>", normal_style))
            for s in final_summary["strengths"]:
                story.append(Paragraph(f"- {s}", normal_style))
            story.append(Spacer(1, 12))

        if final_summary.get("weaknesses"):
            story.append(Paragraph("<b>Weaknesses:</b>", normal_style))
            for w in final_summary["weaknesses"]:
                story.append(Paragraph(f"- {w}", normal_style))
            story.append(Spacer(1, 12))

        if final_summary.get("top_tips"):
            story.append(Paragraph("<b>Top Tips:</b>", normal_style))
            for t in final_summary["top_tips"]:
                story.append(Paragraph(f"- {t}", normal_style))
            story.append(Spacer(1, 12))

        # --- NEW: explicit note about score reduction due to refused/skipped questions ---
        if total_count > 0 and answered_count < total_count:
            missed = total_count - answered_count
            if refused_any:
                note = (
                    f"Note: The overall rating above has been reduced because the candidate "
                    f"refused or skipped {missed} out of {total_count} main questions. "
                    f"The score reflects both answer quality and coverage of questions."
                )
            else:
                note = (
                    f"Note: The overall rating above has been scaled to reflect that the "
                    f"candidate answered only {answered_count} out of {total_count} main questions."
                )
            story.append(Spacer(1, 12))
            story.append(Paragraph(note, normal_style))

    doc.build(story)
    return filename
