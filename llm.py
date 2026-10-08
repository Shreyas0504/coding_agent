import json
import os
import re
import time
from pathlib import PurePosixPath

from dotenv import load_dotenv

load_dotenv()


def _get_setting(name, default=None):
    value = os.getenv(name)
    if value:
        return value

    import streamlit as st

    try:
        return st.secrets.get(name, default)
    except FileNotFoundError:
        return default


# =========================================================
# GEMINI CONFIGURATION
# =========================================================

MODEL_NAME = _get_setting("GEMINI_MODEL", "gemini-3.5-flash-lite")


def get_api_key():
    return _get_setting("GEMINI_API_KEY")


def _require_api_key():
    api_key = get_api_key()

    if not api_key:
        raise RuntimeError(
            "Gemini API key is missing. "
            "Add GEMINI_API_KEY to your .env file and restart the app."
        )

    return api_key


# =========================================================
# JSON PARSER
# =========================================================

def _extract_json_block(text):
    if not text:
        return {}

    text = text.strip()

    # Remove markdown code fences
    text = re.sub(
        r"```json\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"```\s*",
        "",
        text
    )

    # Try parsing the complete response
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting JSON object from extra text
    match = re.search(
        r"\{.*\}",
        text,
        re.DOTALL
    )

    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return {}


# =========================================================
# GEMINI API CALL
# =========================================================

def _call_gemini(prompt):

    api_key = _require_api_key()

    try:
        from google import genai

        client = genai.Client(
            api_key=api_key
        )

        for attempt in range(3):

            try:

                response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=prompt
                )

                text = getattr(
                    response,
                    "text",
                    ""
                ) or ""

                if not text.strip():
                    raise RuntimeError(
                        "Gemini returned an empty response."
                    )

                return text

            except Exception as exc:

                error_text = str(exc)

                # Retry temporary server overload
                if (
                    "503" in error_text
                    or "UNAVAILABLE" in error_text
                ):

                    if attempt < 2:
                        time.sleep(2)
                        continue

                raise RuntimeError(
                    f"Gemini request failed: {exc}"
                ) from exc

    except Exception as exc:

        if str(exc).startswith(
            "Gemini request failed:"
        ):
            raise

        raise RuntimeError(
            f"Gemini request failed: {exc}"
        ) from exc


# =========================================================
# UNDERSTAND TASK
# =========================================================

def understand_task(task, available_files, candidate_files, file_contents):
    if not task or not task.strip():
        raise ValueError("The coding task cannot be empty.")
    if (
        not isinstance(available_files, list)
        or not isinstance(candidate_files, list)
        or any(path not in set(available_files) for path in candidate_files)
        or set(file_contents) != set(candidate_files)
    ):
        raise ValueError("Task understanding received inconsistent project file lists.")

    prompt = f"""
You are a careful junior developer. Interpret the user's request literally.
Summarize only what was requested; do not add implied features or requirements.
Select likely_files only from the RAG CANDIDATE FILES, using their full contents
to verify relevance. RAG results are candidates, not evidence that a file must
change.

Return ONLY valid JSON in exactly this format:
{{
  "task_summary": "short summary",
  "likely_files": ["sample_project/routes.py"],
  "reason": "short reason"
}}

AVAILABLE PROJECT FILES:
{json.dumps(available_files, indent=2)}

RAG CANDIDATE FILES:
{json.dumps(candidate_files, indent=2)}

VERIFIED FULL FILE CONTENTS:
{json.dumps(file_contents, indent=2)}

Select likely_files only from RAG CANDIDATE FILES, which are also members of
AVAILABLE PROJECT FILES. Never invent or rename a file. If no candidate is
relevant, return an empty likely_files list and explain why.

Task:
{task}
"""
    response_text = _call_gemini(prompt)
    data = _extract_json_block(response_text)
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("task_summary"), str)
        or not isinstance(data.get("likely_files"), list)
        or not isinstance(data.get("reason"), str)
    ):
        raise ValueError(
            "Invalid Gemini response for task understanding.\n"
            f"Gemini returned:\n{response_text}"
        )

    allowed_files = set(candidate_files)
    selected_files = []
    for file_path in data["likely_files"]:
        if not isinstance(file_path, str) or file_path not in allowed_files:
            raise ValueError(
                "Gemini selected a file that is not in the available project files: "
                f"{file_path}"
            )
        if file_path not in selected_files:
            selected_files.append(file_path)
    data["likely_files"] = selected_files
    return data


def explicit_new_files(task, available_files):
    if not re.search(r"\b(create|add|write|make|generate)\b", task, re.IGNORECASE):
        return []

    available = set(available_files)
    existing_directories = {"sample_project"}
    for file_path in available_files:
        parent = PurePosixPath(file_path).parent
        while str(parent) != ".":
            existing_directories.add(str(parent))
            parent = parent.parent

    requested_paths = re.findall(
        r"(?<![A-Za-z0-9_./-])sample_project/(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.py",
        task,
    )
    new_files = []
    for file_path in requested_paths:
        parts = PurePosixPath(file_path).parts
        if (
            file_path in available
            or "\\" in file_path
            or any(part in ("", ".", "..") for part in parts)
            or str(PurePosixPath(file_path).parent) not in existing_directories
        ):
            continue
        if file_path not in new_files:
            new_files.append(file_path)
    return new_files


# =========================================================
# CREATE PLAN
# =========================================================

def create_plan(task, available_files, candidate_files, file_contents, understanding):
    prompt = f"""
You are the planning stage of a coding agent.

Your job is ONLY to understand the user's task and create a simple plan.
Do not invent files or requirements. Do not modify code, generate code,
generate patches, or add extra fields to the JSON.

Return ONLY valid JSON with EXACTLY these fields:

{{
  "task": "short description of what the user requested",
  "files_to_read": ["candidate file 1", "candidate file 2"],
  "steps": ["Step 1", "Step 2"]
}}

AVAILABLE FILES (actual files in the project):
{json.dumps(available_files, indent=2)}

CANDIDATE FILES FROM KEYWORD-SIMILARITY RETRIEVAL:
{json.dumps(candidate_files, indent=2)}

FULL CONTENTS ALREADY INSPECTED:
{json.dumps(file_contents, indent=2)}

TASK UNDERSTANDING:
{json.dumps(understanding, indent=2)}

USER TASK:
{task}

Rules:
- files_to_read must contain only exact paths from CANDIDATE FILES above.
- Candidate files are for inspection, not a statement that they must change.
- Prefer existing relevant test files and never use tests/__init__.py as a test.
- If the task asks to add or modify a test, include the relevant existing test file in files_to_read. Prefer an existing test file over creating a new test file when one already exists.
- Reuse existing functionality and keep this plan minimal.
- Every steps item must be a simple string.
"""
    response_text = _call_gemini(prompt)
    data = _extract_json_block(response_text)
    if not isinstance(data, dict):
        raise ValueError(
            "Invalid plan: Gemini did not return a JSON object.\n"
            f"Gemini returned:\n{response_text}"
        )

    if set(data) != {"task", "files_to_read", "steps"}:
        raise ValueError(
            "Invalid plan: expected exactly task, files_to_read, and steps."
        )

    files_to_read = data["files_to_read"]
    steps = data["steps"]
    candidates = set(candidate_files)
    available = set(available_files)
    if not candidates.issubset(available):
        raise ValueError("Invalid plan: candidate files must exist in the project.")
    if (
        not isinstance(data["task"], str)
        or not data["task"].strip()
        or not isinstance(files_to_read, list)
        or any(
            not isinstance(path, str)
            or path not in candidates
            or path not in available
            for path in files_to_read
        )
        or len(files_to_read) != len(set(files_to_read))
        or not isinstance(steps, list)
        or not all(isinstance(step, str) and step.strip() for step in steps)
    ):
        raise ValueError(
            "Invalid plan: expected a task, candidate-only files_to_read, "
            "and simple string steps."
        )

    if re.search(r"\b(test|tests|testing|pytest)\b", task, flags=re.IGNORECASE):
        for source_file in understanding.get("likely_files", []):
            if (
                not isinstance(source_file, str)
                or not source_file.startswith("sample_project/")
                or source_file.startswith("sample_project/tests/")
                or not source_file.endswith(".py")
            ):
                continue
            module_name = source_file.rsplit("/", 1)[-1][:-3]
            test_file = f"sample_project/tests/test_{module_name}.py"
            if test_file in candidates and test_file not in files_to_read:
                files_to_read.append(test_file)

    return data


# =========================================================
# GENERATE CODE CHANGES
# =========================================================

def _normalize_change_request(response_text, allowed_files, allowed_new_files=()):
    data = _extract_json_block(response_text)
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("changes"), list)
        or not isinstance(data.get("explanation"), str)
    ):
        raise ValueError(
            "Invalid Gemini response for code changes.\n"
            f"Gemini returned:\n{response_text}"
        )

    allowed_files = set(allowed_files)
    allowed_new_files = set(allowed_new_files)

    def validate_path(path, permitted):
        if not isinstance(path, str):
            raise ValueError(f"Invalid file path in Gemini response: {path}")
        if path not in permitted or "\\" in path or ".." in path:
            raise ValueError(
                "Gemini selected a path that is not explicitly allowed: "
                f"{path}"
            )
        return path

    seen_files = set()
    for change in data["changes"]:
        if not isinstance(change, dict):
            raise ValueError("Invalid change: expected an object.")
        operation = change.get("operation")
        permitted_paths = allowed_files if operation == "modify" else allowed_new_files
        file_path = validate_path(change.get("file"), permitted_paths)
        if file_path in seen_files:
            raise ValueError(f"Gemini returned multiple changes for {file_path}.")
        seen_files.add(file_path)
        if not isinstance(change.get("description"), str) or not change["description"].strip():
            raise ValueError(f"Change for {file_path} requires a description.")
        if operation == "modify":
            edits = change.get("edits")
            if not isinstance(edits, list) or not edits:
                raise ValueError(f"Change for {file_path} must contain minimal edits.")
            for edit in edits:
                if (
                    not isinstance(edit, dict)
                    or not isinstance(edit.get("search"), str)
                    or not edit["search"]
                    or not isinstance(edit.get("replace"), str)
                    or edit["search"] == edit["replace"]
                ):
                    raise ValueError(
                        f"Change for {file_path} must contain a non-empty exact search "
                        "and a different replacement."
                    )
        elif operation == "create":
            if not isinstance(change.get("content"), str) or not change["content"].strip():
                raise ValueError(f"New file {file_path} requires non-empty content.")
        else:
            raise ValueError("Only modify or explicitly approved create operations are allowed.")

    data["files_to_change"] = [change["file"] for change in data["changes"]]
    return data


def generate_change_request(
    task,
    plan,
    rag_results,
    file_contents,
    allowed_files,
    allowed_new_files,
):
    prompt = f"""
You are a conservative coding assistant. Produce the smallest exact edits that
implement only the user's request. Do not refactor or rewrite full files.
Every search string must occur exactly once in the supplied current file and
the replacement should contain only the requested edit.

Return ONLY valid JSON with this structure:
{{
  "changes": [
    {{
      "file": "sample_project/routes.py",
      "operation": "modify",
      "description": "Add the requested function",
      "edits": [{{"search": "exact original text", "replace": "text after the edit"}}]
    }},
    {{
      "file": "sample_project/new_module.py",
      "operation": "create",
      "description": "Create the explicitly requested file",
      "content": "contents for this new file only"
    }}
  ],
  "explanation": "Explain what changed and why."
}}

You may modify ONLY these task-selected existing files, each also listed in
the approved plan's files_to_read:
{json.dumps(allowed_files, indent=2)}
You may create ONLY exact new paths explicitly named by the user:
{json.dumps(allowed_new_files, indent=2)}
Do not return full file contents for existing files, invent a path, change
signatures, add validation, or modify tests unless the task explicitly
requests it. New-file content is allowed only for the approved new paths.
Reuse existing functions and imports when possible. If adding a route test,
use an existing tests/test_routes.py when it is in the allowlist.

Approved plan:
{json.dumps(plan, indent=2)}

Task:
{task}

RAG candidate snippets (retrieval hints only):
{json.dumps(rag_results, indent=2)}

Verified full file contents from the approved plan:
{json.dumps(file_contents, indent=2)}
"""
    return _normalize_change_request(
        _call_gemini(prompt),
        allowed_files,
        allowed_new_files,
    )


def repair_change_request(
    task,
    plan,
    previous_changes,
    test_output,
    file_contents,
    allowed_files,
):
    prompt = f"""
You are repairing a code change after its pytest run failed. Make one focused
minimal exact edit addressing the reported failure. Do not rewrite files or
make unrelated changes. Each search string must occur exactly once in the
current file.

Return ONLY valid JSON with this structure:
{{
  "changes": [
    {{
      "file": "sample_project/routes.py",
      "operation": "modify",
      "description": "Repair the failing case",
      "edits": [{{"search": "exact current text", "replace": "corrected text"}}]
    }}
  ],
  "explanation": "Explain the repair."
}}

You may modify ONLY these task-approved files or files explicitly created
during the first attempt:
{json.dumps(allowed_files, indent=2)}
Do not create files or return complete file contents.

Task:
{task}

Approved plan:
{json.dumps(plan, indent=2)}

Previous changes:
{json.dumps(previous_changes, indent=2)}

Pytest failure:
{test_output}

Current file contents:
{json.dumps(file_contents, indent=2)}
"""
    return _normalize_change_request(_call_gemini(prompt), allowed_files)


# =========================================================
# SUMMARIZE CHANGES
# =========================================================

def summarize_changes(
    task,
    explanation,
    test_result,
    diff_output
):

    prompt = f"""
Write a short explanation in plain English
of what changed and why.

Return normal plain text.
Do not return JSON.
Do not use markdown code blocks.

Task:
{task}

Explanation:
{explanation}

Test result:
{test_result}

Unified diff:
{diff_output[:2000]}
"""

    summary_text = _call_gemini(
        prompt
    ).strip()

    return {
        "summary": (
            summary_text
            or "The requested change was applied successfully."
        )
    }