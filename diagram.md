flowchart TD
  subgraph UI
    A1[Streamlit UI<br/>CLI (app/main.py)<br/>Buttons: Rephrase/Repeat/Skip]
    A2[API / Integration<br/>(Resume Upload, Webhook)]
  end

  B[Controller (Agentic Loop)<br/>- Ask Q<br/>- Intent detection<br/>- Clarify / Re-ask / Skip<br/>- Follow-up orchestration<br/>- State transitions]

  C1[Heuristics<br/>- Regex<br/>- Token overlap<br/>- Quick refusal/partial checks]
  C2[LLM Services<br/>- Classifier<br/>- Evaluator<br/>- Rephrase / Hint / Follow-up generation<br/>(OpenAI / Mock provider)]
  C3[Follow-up Policy<br/>- Depth control<br/>- followup_depth, MAX]

  D1[State Management<br/>InterviewState<br/>answers[], evaluations[], pending_followup]
  D2[Transcripts & Storage<br/>JSON files (transcripts/)]
  D3[Reporting<br/>PDF export<br/>Charts (report.py)]

  A1 --> B
  A2 --> B
  B --> C1
  B --> C2
  B --> C3
  C1 --> B
  C2 --> B
  C3 --> B
  B --> D1
  B --> D2
  B --> D3

  classDef box fill:#f2f2f2,stroke:#111,stroke-width:1px;
  class A1,A2,B,C1,C2,C3,D1,D2,D3 box;
