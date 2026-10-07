import json
import traceback

import streamlit as st

from agent import analyze_task, run_agent
from llm import get_api_key


st.set_page_config(page_title="AI Coding Agent", page_icon="🤖", layout="wide")


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


st.title("AI Coding Agent")
st.caption("Find → Read → Understand → Plan → Approve → Modify → Test → Diff")
st.caption("RAG: Keyword-similarity retrieval (candidate files only)")

status = st.session_state.get("agent_status", "Ready")

st.subheader("Coding Task")
task = st.text_area(
    "Describe what you want the agent to change",
    placeholder=(
        "Add a get_user_profile function in routes.py that returns a user by "
        "email, and add a test for it."
    ),
    height=120,
)

run_clicked = st.button("▶ Analyze Task & Create Plan", type="primary", use_container_width=True)
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
st.caption(f"Status: {status}")
if status == "Failed":
    st.error("❌ Agent Error")
    st.write(st.session_state.get("agent_error") or "The agent failed without returning an error message.")
    error_traceback = st.session_state.get("agent_traceback", "")
    if error_traceback:
        with st.expander("Developer details"):
            st.code(error_traceback, language="text")
elif status == "Analyzing task...":
    st.info("⏳ Agent is working...")

pending_analysis = st.session_state.get("pending_analysis")
if pending_analysis is not None:
    st.subheader("Review the plan")
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
        approve_clicked = st.button(
            "✅ Approve & Run",
            type="primary",
            use_container_width=True,
        )
    with cancel_col:
        cancel_clicked = st.button("Cancel", use_container_width=True)

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

result = st.session_state.get("agent_result")
if result is None and status not in ("Failed", "Awaiting approval"):
    st.info("Enter a coding task and click Run Coding Agent.")
elif result is not None:
    overview_tab, codebase_tab, changes_tab, tests_tab, diff_tab = st.tabs(
        ["Overview", "Codebase", "Changes", "Tests", "Diff"]
    )

    with overview_tab:
        st.header("TASK")
        st.write(result.get("task", ""))
        st.header("TASK UNDERSTANDING")
        understanding = result.get("task_understanding", {})
        task_summary = _display_text(understanding, "task_summary", "summary")
        if task_summary:
            st.subheader("Task Summary")
            st.write(task_summary)

        reason = _display_text(understanding, "reason")
        if reason:
            st.subheader("Why these files?")
            st.write(reason)

        st.divider()
        st.header("APPROVAL")
        st.success("Plan approved by the user.")
        st.header("AGENT PLAN")
        plan = result.get("plan", {})
        if isinstance(plan, dict):
            st.subheader("Files to read")
            for file_path in _display_list(plan.get("files_to_read", [])):
                st.write(f"📄 {file_path}")
        plan_steps = _display_list(plan.get("steps", []) if isinstance(plan, dict) else [])
        if plan_steps:
            for index, step in enumerate(plan_steps, start=1):
                if isinstance(step, str):
                    st.markdown(f"{index}. {step}")
        else:
            st.caption("No plan was returned.")

        st.divider()
        st.header("FINAL EXPLANATION")
        explanation_text = _display_text(
            result.get("final_explanation", {}), "summary", "explanation", "text"
        )
        if explanation_text:
            st.write(explanation_text)
        else:
            st.caption("No final explanation was returned.")

    with codebase_tab:
        st.header("RAG CANDIDATES")
        st.caption("Keyword-similarity retrieval — candidates for inspection, not an instruction to modify.")
        rag_results = result.get("rag_results", [])
        if isinstance(rag_results, list) and rag_results:
            for index, item in enumerate(rag_results, start=1):
                if not isinstance(item, dict):
                    continue
                file_path = item.get("file_path", "File path not provided")
                chunk = item.get("code_chunk", "")
                with st.expander(f"📄 {file_path} — Result {index}"):
                    if "similarity" in item:
                        st.caption(f"Similarity: {item['similarity']}")
                    if chunk:
                        st.code(chunk, language="python")
                    else:
                        st.caption("No code chunk was returned.")
        else:
            st.caption("No code was retrieved.")

        st.divider()
        st.header("FILES FOUND")
        available_files = _display_list(result.get("available_files", []))
        if available_files:
            for file_path in available_files:
                st.write(f"📄 {file_path}")
        else:
            st.caption("No project files were found.")

        st.divider()
        st.header("FILES SELECTED")
        for file_path in _display_list(result.get("relevant_files", [])):
            st.write(f"📄 {file_path}")

    with changes_tab:
        st.header("WHAT CHANGED?")
        change_payload = result.get("changes", {})
        if not isinstance(change_payload, dict):
            change_payload = {}
        files_changed = _display_list(change_payload.get("files_to_change", []))
        if files_changed:
            for file_path in files_changed:
                st.write(f"📄 {file_path}")
        else:
            st.caption("No files were reported as changed.")

        change_explanation = change_payload.get("explanation")
        if isinstance(change_explanation, str) and change_explanation.strip():
            st.subheader("What changed")
            st.write(change_explanation)

        for change in change_payload.get("changes", []):
            if not isinstance(change, dict):
                continue
            with st.expander(f"{change.get('file', 'Changed file')} — patch details"):
                st.write(change.get("description", ""))
                if change.get("operation") == "create":
                    st.code(change.get("content", ""), language="python")
                else:
                    for edit in change.get("edits", []):
                        st.code(
                            f"− {edit.get('search', '')}\n+ {edit.get('replace', '')}",
                            language="diff",
                        )

    with tests_tab:
        st.header("TESTS")
        test_result = result.get("test_result", {})
        if not isinstance(test_result, dict):
            test_result = {}
        if result.get("repair_attempted"):
            st.info("The first pytest run failed; one repair was attempted.")
        if test_result.get("success") is True:
            st.success("✅ Tests Passed")
        elif test_result.get("success") is False:
            st.error("❌ Tests Failed")
        else:
            st.warning("⏳ Tests Running")
        st.subheader("Test status")
        test_attempts = result.get("test_attempts", [test_result])
        if not test_attempts:
            st.caption("No test output was returned.")
        for index, attempt in enumerate(test_attempts, start=1):
            if not isinstance(attempt, dict):
                continue
            attempt_title = "Initial pytest output" if index == 1 else f"Repair attempt {index} pytest output"
            with st.expander(attempt_title):
                st.code(attempt.get("output") or attempt.get("result") or "No test output.", language="text")

    with diff_tab:
        st.header("DIFF")
        diff_output = result.get("diff") or ""
        if isinstance(diff_output, str) and diff_output.strip():
            st.code(diff_output, language="diff")
        else:
            st.info("No code changes were detected.")

    with st.expander("Developer details"):
        st.code(json.dumps(result, indent=2, ensure_ascii=False, default=str), language="json")
