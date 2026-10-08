import json
import traceback

import streamlit as st

from agent import analyze_task, run_agent
from llm import get_api_key


st.set_page_config(page_title="AI Coding Agent", page_icon="🤖", layout="wide")

st.markdown(
    """
    <style>
        :root {
            --bg: #0b1020;
            --bg-2: #111827;
            --panel: rgba(17, 24, 39, 0.92);
            --panel-strong: #101a2d;
            --panel-soft: #121d33;
            --border: rgba(148, 163, 184, 0.22);
            --text: #e5eefb;
            --muted: #9aa8c7;
            --accent: #4f8cff;
            --accent-2: #8b5cf6;
            --success: #34d399;
            --warning: #fbbf24;
            --danger: #f87171;
            --shadow: 0 10px 30px rgba(15, 23, 42, 0.35);
        }

        .stApp {
            background: linear-gradient(90deg, #020d1a 0%, #091827 20%, #071a2b 100%);
            color: var(--text);
        }

        .block-container {
            padding-top: 1.2rem;
            padding-bottom: 2rem;
            max-width: 1600px;
        }

        [data-testid="stHeader"] {
            background: transparent;
            backdrop-filter: none;
        }

        [data-testid="stToolbar"] {
            display: none;
        }

        .brand-row {
            display: flex;
            align-items: center;
            gap: 0.9rem;
            margin: 0.35rem 0 0.7rem;
            padding-left: 0.15rem;
        }

        .brand-icon {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 42px;
            height: 42px;
            border-radius: 12px;
            background: linear-gradient(135deg, rgba(255,255,255,0.18), rgba(200, 220, 255, 0.08));
            border: 1px solid rgba(148, 163, 184, 0.22);
            color: #eaf2ff;
            font-size: 1.45rem;
            line-height: 1;
            box-shadow: inset 0 0 0 1px rgba(255,255,255,0.04);
        }

        .brand-title {
            font-size: 2.1rem;
            font-weight: 700;
            letter-spacing: -0.06em;
            line-height: 1.1;
            margin: 0;
            color: #f5f7ff;
        }

        .brand-subtitle {
            font-size: 0.74rem;
            letter-spacing: 0.18em;
            text-transform: uppercase;
            color: rgba(163, 177, 204, 0.8);
            margin-top: 0.22rem;
            font-weight: 600;
        }

        .header-side {
            display: flex;
            align-items: center;
            justify-content: flex-end;
            gap: 0.75rem;
            margin-top: 0.5rem;
            margin-bottom: 0.35rem;
        }

        .status-pill {
            display: inline-flex;
            align-items: center;
            gap: 0.55rem;
            padding: 0.5rem 0.8rem;
            border-radius: 999px;
            border: 1px solid var(--border);
            background: rgba(15, 23, 42, 0.7);
            color: var(--text);
            font-size: 0.75rem;
            font-weight: 600;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }

        .status-pill .dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--success);
            box-shadow: 0 0 12px rgba(52, 211, 153, 0.85);
        }

        .status-pill.ready .dot { background: var(--success); box-shadow: 0 0 12px rgba(52, 211, 153, 0.85); }
        .status-pill.analyzing .dot { background: var(--warning); box-shadow: 0 0 12px rgba(251, 191, 36, 0.8); }
        .status-pill.waiting .dot { background: #a78bfa; box-shadow: 0 0 12px rgba(167, 139, 250, 0.75); }
        .status-pill.running .dot { background: var(--accent); box-shadow: 0 0 12px rgba(79, 140, 255, 0.8); }
        .status-pill.completed .dot { background: var(--success); box-shadow: 0 0 12px rgba(52, 211, 153, 0.85); }
        .status-pill.error .dot { background: var(--danger); box-shadow: 0 0 12px rgba(248, 113, 113, 0.8); }

        .deploy-button {
            margin-left: 0.2rem;
            display: flex;
            justify-content: flex-end;
            margin-top: 0.5rem;
        }

        .st-key-deploy_button button {
            background: #1e2f41 !important;
            border: 1px solid #263b50 !important;
            color: #ffffff !important;
            border-radius: 12px !important;
            min-height: 42px !important;
            padding: 0.45rem 1.2rem !important;
            font-size: 0.96rem !important;
            font-weight: 600 !important;
            letter-spacing: 0.02em !important;
            transition: all 0.2s ease !important;
            box-shadow: none !important;
        }

        .st-key-deploy_button button:hover {
            background: #172638 !important;
            border-color: #22364a !important;
            color: #ffffff !important;
        }

        .workflow-shell {
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin: 0.1rem 0 1.1rem;
            padding: 0.9rem 1rem;
            border: 1px solid rgba(148, 163, 184, 0.18);
            border-radius: 14px;
            background: rgba(10, 22, 34, 0.6);
        }

        .workflow-step {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.5rem 0.8rem;
            border-radius: 999px;
            color: rgba(203, 216, 243, 0.82);
            font-size: 0.72rem;
            letter-spacing: 0.16em;
            text-transform: uppercase;
            border: 1px solid transparent;
            background: transparent;
            font-weight: 600;
        }

        .workflow-step.active {
            background: rgba(109, 139, 202, 0.15);
            border-color: rgba(148, 163, 184, 0.26);
            color: #f3f8ff;
            box-shadow: inset 0 0 0 1px rgba(255,255,255,0.02);
        }

        .workflow-arrow {
            color: var(--muted);
            font-size: 1.2rem;
            line-height: 1;
            opacity: 0.8;
        }

        .panel-shell {
            padding: 1.1rem 1.2rem;
            border: 1px solid var(--border);
            border-radius: 18px;
            background: linear-gradient(180deg, rgba(17, 24, 39, 0.82), rgba(15, 23, 42, 0.9));
            box-shadow: var(--shadow);
        }

        .task-shell {
            margin-top: 0.35rem;
            margin-bottom: 1.1rem;
        }

        .section-label {
            font-size: 0.78rem;
            letter-spacing: 0.18em;
            text-transform: uppercase;
            color: var(--muted);
            margin: 0 0 0.75rem;
            font-weight: 700;
        }

        div[data-testid="stTabList"] {
            background: rgba(15, 23, 42, 0.65);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 0.25rem 0.3rem;
            gap: 0.35rem;
        }

        div[role="tab"] {
            border-radius: 10px;
            color: var(--muted);
            padding: 0.55rem 0.9rem !important;
            font-weight: 600;
        }

        div[role="tab"][aria-selected="true"] {
            background: rgba(79, 140, 255, 0.12);
            border: 1px solid rgba(79, 140, 255, 0.35);
            color: #eaf2ff;
        }

        div[data-testid="stTextArea"] {
            border-radius: 16px !important;
            border: 1px solid rgba(148, 163, 184, 0.24) !important;
            background: #0b1020 !important;
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.02);
        }

        div[data-testid="stTextArea"] textarea {
            color: #ffffff !important;
            background: #0b1020 !important;
            caret-color: #ffffff !important;
            font-size: 1rem !important;
            min-height: 120px !important;
            resize: vertical;
        }

        div[data-testid="stTextArea"] textarea::placeholder {
            color: #94a3b8 !important;
            opacity: 1 !important;
        }

        .primary-button button {
            background: linear-gradient(135deg, var(--accent), var(--accent-2)) !important;
            border: 1px solid rgba(96, 165, 250, 0.7) !important;
            color: white !important;
            border-radius: 12px !important;
            min-height: 44px !important;
            font-weight: 700 !important;
            letter-spacing: 0.02em !important;
            box-shadow: 0 14px 30px rgba(79, 140, 255, 0.2) !important;
        }

        .primary-button button:hover {
            filter: brightness(1.05);
            transform: translateY(-1px);
        }

        .status-card {
            display: flex;
            align-items: center;
            gap: 0.8rem;
            padding: 1rem 1.1rem;
            border: 1px solid var(--border);
            border-radius: 16px;
            background: rgba(15, 23, 42, 0.7);
            margin: 0.2rem 0 1.2rem;
        }

        .status-card.ready { border-color: rgba(52, 211, 153, 0.3); background: rgba(6, 31, 26, 0.42); }
        .status-card.analyzing { border-color: rgba(251, 191, 36, 0.3); background: rgba(41, 30, 9, 0.4); }
        .status-card.waiting { border-color: rgba(167, 139, 250, 0.4); background: rgba(27, 20, 40, 0.42); }
        .status-card.running { border-color: rgba(79, 140, 255, 0.35); background: rgba(11, 22, 38, 0.45); }
        .status-card.completed { border-color: rgba(52, 211, 153, 0.35); background: rgba(3, 26, 21, 0.42); }
        .status-card.error { border-color: rgba(248, 113, 113, 0.35); background: rgba(52, 12, 12, 0.4); }

        .status-head {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 13px;
            height: 13px;
            border-radius: 50%;
            background: var(--success);
            box-shadow: 0 0 18px rgba(52, 211, 153, 0.7);
            flex-shrink: 0;
        }

        .status-card.ready .status-head { background: var(--success); }
        .status-card.analyzing .status-head { background: var(--warning); }
        .status-card.waiting .status-head { background: #a78bfa; }
        .status-card.running .status-head { background: var(--accent); }
        .status-card.completed .status-head { background: var(--success); }
        .status-card.error .status-head { background: var(--danger); }

        .status-inner {
            display: flex;
            flex-direction: column;
            gap: 0.15rem;
        }

        .status-label {
            font-size: 0.68rem;
            letter-spacing: 0.16em;
            text-transform: uppercase;
            color: var(--muted);
            font-weight: 700;
        }

        .status-title {
            font-size: 1.15rem;
            font-weight: 700;
            color: var(--text);
            letter-spacing: 0.02em;
        }

        .status-message {
            color: var(--muted);
            font-size: 0.92rem;
        }

        .soft-card {
            padding: 1rem 1.1rem;
            border-radius: 16px;
            border: 1px solid var(--border);
            background: rgba(15, 23, 42, 0.62);
            min-height: 125px;
        }

        .soft-card h4 {
            margin: 0 0 0.7rem;
            font-size: 0.72rem;
            letter-spacing: 0.14em;
            text-transform: uppercase;
            color: var(--muted);
        }

        .soft-card p, .soft-card li {
            color: var(--text);
            line-height: 1.6;
            margin: 0;
        }

        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0,1fr));
            gap: 1rem;
            margin-top: 0.5rem;
        }

        .file-tree {
            display: flex;
            flex-direction: column;
            gap: 0.4rem;
            margin-top: 0.4rem;
        }

        .tree-row {
            display: flex;
            align-items: center;
            gap: 0.55rem;
            padding: 0.5rem 0.6rem;
            border-radius: 10px;
            background: rgba(17, 24, 39, 0.38);
            border: 1px solid rgba(148, 163, 184, 0.12);
            color: var(--text);
            font-size: 0.96rem;
        }

        .tree-row.root {
            background: rgba(79, 140, 255, 0.08);
            border-color: rgba(79, 140, 255, 0.2);
            font-weight: 600;
        }

        .tree-row.child {
            margin-left: 1.2rem;
        }

        .file-pill {
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
            padding: 0.4rem 0.7rem;
            border: 1px solid var(--border);
            background: rgba(17, 24, 39, 0.5);
            border-radius: 999px;
            color: var(--text);
            font-size: 0.8rem;
            margin: 0.18rem 0.25rem 0.18rem 0;
        }

        .status-badge {
            display: inline-flex;
            align-items: center;
            padding: 0.3rem 0.6rem;
            border-radius: 999px;
            font-size: 0.7rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            font-weight: 700;
            border: 1px solid rgba(148, 163, 184, 0.22);
            background: rgba(79, 140, 255, 0.08);
            color: #dfe9ff;
        }

        .status-badge.modified { background: rgba(79, 140, 255, 0.08); color: #dfe9ff; }
        .status-badge.added { background: rgba(52, 211, 153, 0.08); color: #c7f9d7; }
        .status-badge.deleted { background: rgba(248, 113, 113, 0.08); color: #fecaca; }

        .change-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 1rem;
            padding: 0.8rem 0.9rem;
            border: 1px solid var(--border);
            border-radius: 12px;
            background: rgba(15, 23, 42, 0.45);
            margin-bottom: 0.7rem;
        }

        .code-panel {
            background: rgba(2, 6, 23, 0.85);
            border: 1px solid rgba(148, 163, 184, 0.18);
            border-radius: 12px;
            padding: 0.7rem 0.85rem;
            margin-top: 0.8rem;
        }

        .test-result {
            display: inline-flex;
            align-items: center;
            gap: 0.55rem;
            padding: 0.5rem 0.8rem;
            border-radius: 12px;
            font-size: 1.05rem;
            font-weight: 700;
            margin-bottom: 0.7rem;
            border: 1px solid rgba(148, 163, 184, 0.18);
        }

        .test-result.success {
            background: rgba(52, 211, 153, 0.10);
            color: #d9fff2;
            border-color: rgba(52, 211, 153, 0.28);
        }

        .test-result.failure {
            background: rgba(248, 113, 113, 0.10);
            color: #ffdada;
            border-color: rgba(248, 113, 113, 0.3);
        }

        .info-banner {
            background: rgba(79, 140, 255, 0.08);
            border: 1px solid rgba(79, 140, 255, 0.25);
            border-radius: 12px;
            padding: 0.85rem 0.9rem;
            color: var(--text);
            margin: 0.6rem 0 0.9rem;
        }

        .error-banner {
            background: rgba(248, 113, 113, 0.08);
            border: 1px solid rgba(248, 113, 113, 0.25);
            border-radius: 12px;
            padding: 0.85rem 0.9rem;
            color: #ffdada;
            margin: 0.6rem 0 0.9rem;
        }

        .status-pill-wrap { display: flex; align-items: center; justify-content: flex-end; }
        .glow, .glow:hover { transition: all 0.2s ease; }

        @media (max-width: 900px) {
            .dashboard-grid { grid-template-columns: 1fr; }
            .brand-title { font-size: 1.5rem; }
            .header-side { justify-content: flex-start; flex-wrap: wrap; }
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def _display_text(value, *keys):
    """Return readable text from the plain-text or small-dict values the agent returns."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in keys:
            content = value.get(key)
            if isinstance(content, str):
                return content
        return ""
    return ""


def _display_list(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        return [value]
    return []


def _get_status_meta(status):
    normalized = (status or "Ready").strip()
    state_map = {
        "Ready": ("ready", "READY", "Agent ready"),
        "Analyzing task...": ("analyzing", "ANALYZING", "Reviewing the task and codebase"),
        "Awaiting approval": ("waiting", "WAITING FOR APPROVAL", "Review the proposed plan before continuing"),
        "Agent is working...": ("running", "RUNNING", "Applying changes and validating with pytest"),
        "Completed": ("completed", "COMPLETED", "Agent finished the requested task"),
        "Failed": ("error", "ERROR", "The agent encountered an error"),
    }
    return state_map.get(normalized, ("ready", "READY", "Agent ready"))


def _render_status_card(status):
    state, label, message = _get_status_meta(status)
    return f"""
    <div class="status-card {state}">
        <div class="status-head"></div>
        <div class="status-inner">
            <div class="status-label">{label}</div>
            <div class="status-title">{message}</div>
        </div>
    </div>
    """


def _render_workflow(status):
    state_index = {
        "Ready": 0,
        "Analyzing task...": 1,
        "Awaiting approval": 3,
        "Agent is working...": 4,
        "Completed": 6,
        "Failed": 6,
    }
    current_index = state_index.get(status, 0)
    steps = [
        "01 Find",
        "02 Understand",
        "03 Plan",
        "04 Approve",
        "05 Modify",
        "06 Test",
        "07 Diff",
    ]
    formatted = []
    for index, step in enumerate(steps):
        active = " active" if index == current_index else ""
        formatted.append(f'<div class="workflow-step{active}">{step}</div>')
        if index < len(steps) - 1:
            formatted.append('<div class="workflow-arrow">→</div>')
    return f'<div class="workflow-shell">{"".join(formatted)}</div>'


status = st.session_state.get("agent_status", "Ready")

header_col, side_col = st.columns([5, 2.4])
with header_col:
    st.markdown(
        """
        <div class="brand-row">
            <div class="brand-icon">⌘</div>
            <div>
                <div class="brand-title">AI Coding Agent</div>
                <div class="brand-subtitle">Understand • Plan • Approve • Modify • Test</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with side_col:
    st.markdown('<div class="deploy-button">', unsafe_allow_html=True)
    st.button("Deploy", key="deploy_button", help="Open deployment information", use_container_width=False)
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown(_render_workflow(status), unsafe_allow_html=True)

st.markdown('<div class="section-label" style="margin-top: 1rem;">WHAT DO YOU WANT TO CHANGE?</div>', unsafe_allow_html=True)
task = st.text_area(
    "Describe what you want the agent to change",
    label_visibility="collapsed",
    placeholder=(
        "e.g. Add a get_user_profile function and create a test for it."
    ),
    height=120,
)

st.markdown('<div class="primary-button">', unsafe_allow_html=True)
run_clicked = st.button(
    "Analyze Task",
    type="primary",
    use_container_width=False,
    key="analyze_task_button",
)
st.markdown('</div>', unsafe_allow_html=True)
if run_clicked:
    if not task.strip():
        st.warning("Please enter a coding task before running the agent.")
    elif not get_api_key():
        st.session_state.agent_status = "Failed"
        st.session_state.agent_error = (
            "Gemini API key is missing. Add GEMINI_API_KEY to your .env file and restart the app."
        )
        st.session_state.agent_traceback = ""
        st.session_state.agent_result = None
        st.session_state.pending_analysis = None
    else:
        st.session_state.agent_status = "Analyzing task..."
        st.session_state.agent_result = None
        st.session_state.agent_error = None
        st.session_state.agent_traceback = ""
        st.session_state.pending_analysis = None
        with st.spinner("⏳ Agent is working..."):
            try:
                st.session_state.pending_analysis = analyze_task(task)
                st.session_state.agent_status = "Awaiting approval"
            except Exception as exc:
                st.session_state.agent_status = "Failed"
                st.session_state.agent_error = str(exc)
                st.session_state.agent_traceback = traceback.format_exc()

status = st.session_state.get("agent_status", "Ready")

st.markdown(_render_status_card(status), unsafe_allow_html=True)
if status == "Failed":
    st.markdown(
        f"<div class='error-banner'><strong>Agent Error</strong><br>{st.session_state.get('agent_error') or 'The agent failed without returning an error message.'}</div>",
        unsafe_allow_html=True,
    )
    error_traceback = st.session_state.get("agent_traceback", "")
    if error_traceback:
        with st.expander("Developer details"):
            st.code(error_traceback, language="text")
elif status == "Analyzing task...":
    st.markdown("<div class='info-banner'>⏳ Agent is working...</div>", unsafe_allow_html=True)

pending_analysis = st.session_state.get("pending_analysis")
if pending_analysis is not None:
    st.markdown('<div class="panel-shell">', unsafe_allow_html=True)
    st.markdown('<div class="section-label" style="margin-bottom: 0.6rem;">Review the plan</div>', unsafe_allow_html=True)
    understanding = pending_analysis["task_understanding"]
    st.markdown("**Task**")
    st.write(pending_analysis["task"])
    st.markdown("**Task understanding**")
    st.write(understanding["task_summary"])
    st.caption(understanding["reason"])

    st.markdown("**Files found**")
    for file_path in pending_analysis["available_files"]:
        st.write(f"📄 {file_path}")

    st.markdown("**RAG Candidates — Keyword-similarity retrieval**")
    for item in pending_analysis["rag_results"]:
        st.write(f"📄 {item['file_path']} · similarity {item['similarity']}")

    st.markdown("**Files selected**")
    for file_path in understanding["likely_files"]:
        st.write(f"📄 {file_path}")
    st.caption("Why these files? " + understanding["reason"])

    plan = pending_analysis["plan"]
    with st.expander("Files read and verified"):
        for file_path in plan["files_to_read"]:
            st.write(f"📄 {file_path}")
            st.code(pending_analysis["file_contents"][file_path], language="python")

    st.markdown("**Agent plan**")
    for index, step in enumerate(plan["steps"], start=1):
        st.markdown(f"{index}. {step}")

    st.markdown("**Approval**")
    approve_col, cancel_col = st.columns(2)
    with approve_col:
        st.markdown('<div class="primary-button">', unsafe_allow_html=True)
        approve_clicked = st.button(
            "Approve & Run",
            type="primary",
            use_container_width=True,
            key="run_approved_agent",
        )
        st.markdown('</div>', unsafe_allow_html=True)
    with cancel_col:
        cancel_clicked = st.button("Cancel", use_container_width=True, key="cancel_approval")

    if approve_clicked:
        st.session_state.agent_status = "Agent is working..."
        st.session_state.agent_result = None
        st.session_state.agent_error = None
        st.session_state.agent_traceback = ""
        with st.spinner("⏳ Applying changes in a temporary copy, then running pytest..."):
            try:
                st.session_state.agent_result = run_agent(pending_analysis)
                st.session_state.agent_status = "Completed"
                st.session_state.pending_analysis = None
            except Exception as exc:
                st.session_state.agent_status = "Failed"
                st.session_state.agent_error = str(exc)
                st.session_state.agent_traceback = traceback.format_exc()
                st.session_state.pending_analysis = None
        st.rerun()
    elif cancel_clicked:
        st.session_state.pending_analysis = None
        st.session_state.agent_status = "Ready"
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

result = st.session_state.get("agent_result")
if result is None and status not in ("Failed", "Awaiting approval"):
    st.markdown("<div class='info-banner'>Enter a coding task and click Analyze Task.</div>", unsafe_allow_html=True)
elif result is not None:
    overview_tab, codebase_tab, changes_tab, tests_tab, diff_tab = st.tabs(
        ["Overview", "Codebase", "Changes", "Tests", "Diff"]
    )

    with overview_tab:
        st.markdown('<div class="dashboard-grid">', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(
                """
                <div class="soft-card">
                    <h4>TASK</h4>
                    <p>""" + str(result.get("task", "")) + """</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            understanding = result.get("task_understanding", {})
            task_summary = _display_text(understanding, "task_summary", "summary")
            reason = _display_text(understanding, "reason")
            st.markdown(
                f"""
                <div class="soft-card">
                    <h4>TASK UNDERSTANDING</h4>
                    <p><strong>Summary:</strong> {task_summary or 'No summary was returned.'}</p>
                    <p style="margin-top: 0.65rem;"><strong>Why these files?</strong> {reason or 'No rationale was returned.'}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col2:
            relevant_files = _display_list(result.get("relevant_files", [])) or _display_list(result.get("available_files", []))
            file_html = "".join(f'<div class="file-pill">📄 {file_path}</div>' for file_path in relevant_files)
            st.markdown(
                f"""
                <div class="soft-card">
                    <h4>RELEVANT FILES</h4>
                    {file_html or '<p>No relevant files were returned.</p>'}
                </div>
                """,
                unsafe_allow_html=True,
            )
            plan = result.get("plan", {})
            plan_steps = _display_list(plan.get("steps", []) if isinstance(plan, dict) else [])
            steps_html = "".join(f'<li>{index}. {step}</li>' for index, step in enumerate(plan_steps, start=1) if isinstance(step, str)) or "<li>No plan was returned.</li>"
            st.markdown(
                f"""
                <div class="soft-card">
                    <h4>PLAN</h4>
                    <ul>{steps_html}</ul>
                </div>
                """,
                unsafe_allow_html=True,
            )
        approval_text = "Waiting for approval" if status == "Awaiting approval" else "Approved"
        approval_style = "status-badge modified" if status == "Awaiting approval" else "status-badge added"
        st.markdown(
            f"""
            <div class="soft-card" style="grid-column: 1 / -1; min-height: auto;">
                <h4>APPROVAL</h4>
                <div class="{approval_style}">{approval_text}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)

    with codebase_tab:
        st.markdown('<div class="panel-shell">', unsafe_allow_html=True)
        st.markdown('<div class="section-label" style="margin-bottom: 0.5rem;">PROJECT</div>', unsafe_allow_html=True)
        st.markdown('<div class="tree-row root">📁 sample_project/</div>', unsafe_allow_html=True)
        project_files = [
            "routes.py",
            "database.py",
            "validators.py",
            "tests/test_routes.py",
            "tests/test_validators.py",
        ]
        for file_path in project_files:
            kind = "folder" if file_path.startswith("tests/") else "file"
            icon = "📁" if kind == "folder" else "📄"
            css_class = "tree-row child" if file_path.startswith("tests/") else "tree-row"
            st.markdown(f'<div class="{css_class}">{icon} {file_path}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with changes_tab:
        st.markdown('<div class="panel-shell">', unsafe_allow_html=True)
        st.markdown('<div class="section-label">FILES CHANGED</div>', unsafe_allow_html=True)
        change_payload = result.get("changes", {})
        if not isinstance(change_payload, dict):
            change_payload = {}
        changes_list = change_payload.get("changes", [])
        if not changes_list:
            files_changed = _display_list(change_payload.get("files_to_change", []))
            if files_changed:
                for file_path in files_changed:
                    st.markdown(f'<div class="change-row"><span>{file_path}</span><span class="status-badge modified">Modified</span></div>', unsafe_allow_html=True)
            else:
                st.info("No files were reported as changed.")
        else:
            for change in changes_list:
                if not isinstance(change, dict):
                    continue
                file_name = change.get("file", "Changed file")
                operation = change.get("operation", "modified")
                badge_class = {
                    "create": "added",
                    "delete": "deleted",
                    "modify": "modified",
                    "modified": "modified",
                }.get(operation, "modified")
                label = {
                    "create": "Added",
                    "delete": "Deleted",
                    "modify": "Modified",
                    "modified": "Modified",
                }.get(operation, "Modified")
                st.markdown(
                    f'<div class="change-row"><span>{file_name}</span><span class="status-badge {badge_class}">{label}</span></div>',
                    unsafe_allow_html=True,
                )
        st.markdown('</div>', unsafe_allow_html=True)

    with tests_tab:
        st.markdown('<div class="panel-shell">', unsafe_allow_html=True)
        st.markdown('<div class="section-label">TEST RESULT</div>', unsafe_allow_html=True)
        test_result = result.get("test_result", {})
        if not isinstance(test_result, dict):
            test_result = {}
        success = test_result.get("success")
        if success is True:
            st.markdown('<div class="test-result success">✓ Tests passed</div>', unsafe_allow_html=True)
        elif success is False:
            st.markdown('<div class="test-result failure">✕ Tests failed</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="test-result">⏳ Test run in progress</div>', unsafe_allow_html=True)

        execution_result = result.get("execution_result") or {}
        if isinstance(execution_result, dict):
            if execution_result.get("available") is True:
                st.markdown('<div class="section-label" style="margin-top: 1rem;">EXECUTION RESULT</div>', unsafe_allow_html=True)
                st.markdown(
                    f"<div class='panel-shell' style='padding: 0.8rem; margin-top: 0.5rem; background: rgba(3, 26, 21, 0.42); border-color: rgba(52, 211, 153, 0.25);'>"
                    f"<div><strong>Function:</strong> {execution_result.get('function', 'unknown')}</div>"
                    f"<div><strong>Arguments:</strong> {execution_result.get('arguments', [])}</div>"
                    f"<div><strong>Output:</strong> {execution_result.get('output', 'N/A')}</div>"
                    f"<div style='margin-top: 0.4rem; color: #d9fff2;'>✓ Execution successful</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown('<div class="section-label" style="margin-top: 1rem;">EXECUTION RESULT</div>', unsafe_allow_html=True)
                st.info(execution_result.get("message", "Execution result is not available for this change."))

        test_attempts = result.get("test_attempts", [test_result])
        if not test_attempts:
            st.caption("No test output was returned.")
        for index, attempt in enumerate(test_attempts, start=1):
            if not isinstance(attempt, dict):
                continue
            attempt_title = "Initial pytest output" if index == 1 else f"Repair attempt {index} pytest output"
            with st.expander(attempt_title):
                st.code(attempt.get("output") or attempt.get("result") or "No test output.", language="text")
        st.markdown('</div>', unsafe_allow_html=True)

    with diff_tab:
        st.markdown('<div class="panel-shell">', unsafe_allow_html=True)
        st.markdown('<div class="section-label">DIFF</div>', unsafe_allow_html=True)
        diff_output = result.get("diff") or ""
        if isinstance(diff_output, str) and diff_output.strip():
            st.code(diff_output, language="diff")
        else:
            st.info("No code changes were detected.")
        st.markdown('</div>', unsafe_allow_html=True)

    with st.expander("Developer details"):
        st.code(json.dumps(result, indent=2, ensure_ascii=False, default=str), language="json")
