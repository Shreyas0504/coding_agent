import difflib
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SAMPLE_PROJECT_DIR = PROJECT_ROOT / "sample_project"


def _safe_path(path, project_root=PROJECT_ROOT):
    if not path:
        raise ValueError("A file path is required.")

    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = (project_root / candidate).resolve()
    else:
        candidate = candidate.resolve()

    sample_project_root = (project_root / "sample_project").resolve()
    if candidate != sample_project_root and sample_project_root not in candidate.parents:
        raise ValueError("Invalid file path. Only files inside sample_project are allowed.")

    return candidate


def _require_working_copy(project_root):
    working_root = Path(project_root).resolve()
    if working_root == PROJECT_ROOT.resolve():
        raise ValueError("The source sample_project is read-only.")
    if not (working_root / "sample_project").is_dir():
        raise FileNotFoundError("The temporary project copy was not found.")
    return working_root


def list_files(project_root=PROJECT_ROOT):
    project_root = Path(project_root).resolve()
    sample_project_root = (project_root / "sample_project").resolve()
    if not sample_project_root.is_dir():
        raise FileNotFoundError("sample_project folder was not found.")
    return [
        str(path.relative_to(project_root)).replace("\\", "/")
        for path in sorted(sample_project_root.rglob("*.py"))
    ]


def read_file(path, project_root=PROJECT_ROOT):
    safe_file = _safe_path(path, project_root)
    if not safe_file.exists():
        raise FileNotFoundError(f"File not found: {path}")
    return safe_file.read_text(encoding="utf-8")


def search_code(query):
    if not query or not query.strip():
        return []

    matches = []
    for file_path in list_files():
        content = read_file(file_path)
        if query.lower() in content.lower():
            matches.append({"file": file_path, "content": content})
    return matches


def write_file(path, content, project_root):
    project_root = _require_working_copy(project_root)
    safe_file = _safe_path(path, project_root)
    safe_file.parent.mkdir(parents=True, exist_ok=True)
    safe_file.write_text(content, encoding="utf-8")
    return str(safe_file.relative_to(project_root)).replace("\\", "/")


def apply_change_request(
    change_request,
    allowed_files,
    project_root,
    allowed_new_files=(),
):
    project_root = _require_working_copy(project_root)
    allowed_files = set(allowed_files)
    allowed_new_files = set(allowed_new_files)
    applied = []

    for change in change_request.get("changes", []):
        file_path = change.get("file")
        operation = change.get("operation")
        if operation == "create":
            if (
                not isinstance(file_path, str)
                or file_path not in allowed_new_files
                or not file_path.startswith("sample_project/")
                or "\\" in file_path
                or ".." in file_path.split("/")
            ):
                raise ValueError(f"Refusing to create an unapproved file: {file_path}")
            safe_file = _safe_path(file_path, project_root)
            if safe_file.suffix != ".py":
                raise ValueError("Only explicitly requested Python files may be created.")
            if not safe_file.parent.is_dir():
                raise ValueError(
                    f"Cannot create {file_path}: its parent directory does not exist."
                )
            content = change.get("content")
            if not isinstance(content, str) or not content.strip():
                raise ValueError(f"New file {file_path} requires non-empty content.")
            try:
                with safe_file.open("x", encoding="utf-8") as handle:
                    handle.write(content)
            except FileExistsError as exc:
                raise ValueError(f"Refusing to overwrite existing file: {file_path}") from exc
            applied.append(file_path)
            continue

        if operation != "modify" or file_path not in allowed_files:
            raise ValueError(f"Refusing to modify an unapproved file: {file_path}")

        content = read_file(file_path, project_root=project_root)
        for edit in change.get("edits", []):
            search_text = edit.get("search")
            replacement = edit.get("replace")
            occurrences = content.count(search_text)
            if occurrences != 1:
                raise ValueError(
                    f"Patch for {file_path} did not match exactly once "
                    f"(found {occurrences} matches); no change was applied."
                )
            content = content.replace(search_text, replacement, 1)

        original_content = read_file(file_path, project_root=project_root)
        if content == original_content:
            raise ValueError(f"Patch for {file_path} did not change the file.")
        write_file(file_path, content, project_root=project_root)
        applied.append(file_path)

    return applied


def run_tests(project_root):
    project_root = _require_working_copy(project_root)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
    )

    output = (result.stdout or "") + (result.stderr or "")
    return {
        "success": result.returncode == 0,
        "return_code": result.returncode,
        "output": output.strip(),
    }


def generate_diff(project_root, original_project_root=PROJECT_ROOT):
    original_files = set(list_files(original_project_root))
    modified_files = set(list_files(project_root))
    diff_parts = []

    for file_path in sorted(original_files | modified_files):
        original_path = original_project_root / file_path
        modified_path = project_root / file_path
        original_content = (
            original_path.read_text(encoding="utf-8").splitlines(keepends=True)
            if original_path.exists()
            else []
        )
        modified_content = (
            modified_path.read_text(encoding="utf-8").splitlines(keepends=True)
            if modified_path.exists()
            else []
        )
        if original_content == modified_content:
            continue

        diff_parts.extend(
            difflib.unified_diff(
                original_content,
                modified_content,
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}",
            )
        )

    return "".join(diff_parts).strip()


@contextmanager
def temporary_project_copy():
    with tempfile.TemporaryDirectory(prefix="ai-coding-agent-") as temp_dir:
        temp_root = Path(temp_dir)
        shutil.copytree(
            SAMPLE_PROJECT_DIR,
            temp_root / "sample_project",
            ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc"),
        )
        yield temp_root
