import ast
import importlib
import re
import sys

from llm import (
    create_plan,
    generate_change_request,
    repair_change_request,
    summarize_changes,
    understand_task,
    explicit_new_files,
)
from rag import retrieve_relevant_code
from tools import (
    apply_change_request,
    generate_diff,
    list_files,
    read_file,
    run_tests,
    temporary_project_copy,
)


def _extract_task_numbers(task):
    if not isinstance(task, str):
        return []
    values = []
    for match in re.finditer(r"-?\d+(?:\.\d+)?", task):
        number = match.group(0)
        values.append(float(number) if "." in number else int(number))
    return values


def _task_requests_tests(task):
    return bool(re.search(r"\b(test|tests|testing|pytest)\b", task, re.IGNORECASE))


def _related_existing_test_files(source_files, available_files):
    available = set(available_files)
    test_files = []
    for source_file in source_files:
        if (
            not isinstance(source_file, str)
            or not source_file.startswith("sample_project/")
            or source_file.startswith("sample_project/tests/")
            or not source_file.endswith(".py")
        ):
            continue
        module_name = source_file.rsplit("/", 1)[-1][:-3]
        test_file = f"sample_project/tests/test_{module_name}.py"
        if test_file in available and test_file not in test_files:
            test_files.append(test_file)
    return test_files


def _detect_operation(task):
    if not isinstance(task, str):
        return None
    lowered = task.lower()
    operation_keywords = {
        "add": ["add", "addition", "plus", "sum", "total", "increase"],
        "multiply": ["multiply", "product", "times", "multiplied"],
        "subtract": ["subtract", "difference", "minus", "decrease"],
        "average": ["average", "avg", "mean"],
        "is_even": ["even", "is_even", "parity"],
    }
    for operation, keywords in operation_keywords.items():
        if any(keyword in lowered for keyword in keywords):
            return operation
    return None


def _function_matches_operation(function_name, operation):
    name = re.sub(r"[^a-z0-9]", "", function_name.lower())
    operation_aliases = {
        "add": ["add", "sum", "total"],
        "multiply": ["multiply", "product"],
        "subtract": ["subtract", "difference", "minus"],
        "average": ["average", "mean", "avg"],
        "is_even": ["iseven", "even", "parity"],
    }
    aliases = operation_aliases.get(operation, [])
    return any(alias in name for alias in aliases)


def _get_function_definitions(project_root, file_paths):
    functions = []
    for file_path in file_paths:
        if not file_path.startswith("sample_project/") or not file_path.endswith(".py"):
            continue
        try:
            source = read_file(file_path, project_root=project_root)
            tree = ast.parse(source)
        except Exception:
            continue
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                functions.append({
                    "file": file_path,
                    "name": node.name,
                    "arg_count": len(node.args.args) + len(node.args.kwonlyargs),
                })
    return functions


def _safe_run_generated_function(task, project_root, change_request=None):
    unavailable = {
        "available": False,
        "success": False,
        "message": "Execution result is not available for this change.",
    }

    if not isinstance(task, str) or not task.strip():
        return unavailable

    numbers = _extract_task_numbers(task)
    if not numbers:
        return unavailable

    operation = _detect_operation(task)
    files_to_scan = []
    if isinstance(change_request, dict):
        for change in change_request.get("changes", []):
            if isinstance(change, dict):
                file_path = change.get("file")
                if isinstance(file_path, str):
                    files_to_scan.append(file_path)
        for file_path in change_request.get("files_to_change", []):
            if isinstance(file_path, str):
                files_to_scan.append(file_path)
    files_to_scan = list(dict.fromkeys(files_to_scan))
    if not files_to_scan:
        files_to_scan = list_files(project_root)

    functions = _get_function_definitions(project_root, files_to_scan)
    if not functions:
        return unavailable

    matching_function = None
    if operation:
        matches = [
            item for item in functions
            if _function_matches_operation(item["name"], operation)
        ]
        if matches:
            matching_function = matches[0]
    if matching_function is None and len(functions) == 1:
        matching_function = functions[0]
    if matching_function is None:
        return unavailable

    desired_count = matching_function["arg_count"] or 1
    if operation == "average":
        desired_count = max(1, min(len(numbers), max(3, desired_count)))
        desired_count = max(3, min(len(numbers), desired_count))
        if len(numbers) < 3:
            return unavailable
    elif operation == "is_even":
        desired_count = 1
    elif operation in {"add", "multiply", "subtract"}:
        desired_count = min(2, len(numbers))
        if desired_count < 2:
            return unavailable
    else:
        desired_count = min(desired_count, len(numbers))
        if desired_count < 1:
            return unavailable

    args = numbers[:desired_count]
    if operation == "average":
        args = numbers[:3]
    if operation == "is_even":
        args = [numbers[0]]
    if operation in {"add", "multiply", "subtract"}:
        args = numbers[:2]

    module_name = matching_function["file"].replace("/", ".")[:-3]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    try:
        module = importlib.import_module(module_name)
        if not hasattr(module, matching_function["name"]):
            return unavailable
        function = getattr(module, matching_function["name"])
        output = function(*args)
    except Exception:
        return unavailable

    return {
        "function": matching_function["name"],
        "arguments": [int(value) if isinstance(value, float) and value.is_integer() else value for value in args],
        "output": output,
        "success": True,
        "available": True,
    }


def analyze_task(task):
    if not task or not task.strip():
        raise ValueError("The coding task cannot be empty.")

    available_files = list_files()
    if not available_files:
        raise FileNotFoundError("No Python files were found in sample_project.")

    rag_results = retrieve_relevant_code(task, top_k=5, file_paths=available_files)
    candidate_files = list(dict.fromkeys(item["file_path"] for item in rag_results))
    if not candidate_files:
        raise ValueError("Keyword-similarity retrieval found no candidate project files.")

    file_contents = {
        file_path: read_file(file_path)
        for file_path in candidate_files
    }
    task_understanding = understand_task(
        task,
        available_files,
        candidate_files,
        file_contents,
    )
    if _task_requests_tests(task):
        related_tests = _related_existing_test_files(
            task_understanding["likely_files"],
            available_files,
        )
        for test_file in related_tests:
            if test_file not in candidate_files:
                candidate_files.append(test_file)
                file_contents[test_file] = read_file(test_file)
            if test_file not in task_understanding["likely_files"]:
                task_understanding["likely_files"].append(test_file)
    requested_new_files = explicit_new_files(task, available_files)
    if not task_understanding["likely_files"] and not requested_new_files:
        raise ValueError(
            "No retrieved candidate files appear relevant to the task. "
            "Please clarify the requested feature or rephrase the task."
        )

    plan = create_plan(
        task,
        available_files,
        candidate_files,
        file_contents,
        task_understanding,
    )
    return {
        "task": task,
        "available_files": available_files,
        "candidate_files": candidate_files,
        "requested_new_files": requested_new_files,
        "file_contents": file_contents,
        "task_understanding": task_understanding,
        "rag_results": rag_results,
        "relevant_files": task_understanding["likely_files"],
        "plan": plan,
    }


def run_agent(approved_analysis):
    if not isinstance(approved_analysis, dict):
        raise ValueError("An approved task analysis is required.")

    task = approved_analysis.get("task")
    available_files = approved_analysis.get("available_files")
    candidate_files = approved_analysis.get("candidate_files")
    requested_new_files = approved_analysis.get("requested_new_files")
    plan = approved_analysis.get("plan")
    if not isinstance(task, str) or not task.strip():
        raise ValueError("The approved analysis has no valid coding task.")
    if (
        not isinstance(available_files, list)
        or not isinstance(candidate_files, list)
        or not isinstance(requested_new_files, list)
        or not isinstance(plan, dict)
        or not isinstance(plan.get("files_to_read"), list)
    ):
        raise ValueError("The approved analysis has invalid file lists.")
    if any(
        not isinstance(path, str)
        for path in available_files + candidate_files + requested_new_files
    ) or any(not isinstance(path, str) for path in plan["files_to_read"]):
        raise ValueError("The approved analysis contains a non-text file path.")

    current_files = list_files()
    if current_files != available_files:
        raise ValueError("The sample-project file list changed after analysis.")
    if any(path not in set(available_files) for path in candidate_files):
        raise ValueError("The approved analysis contains an unavailable candidate file.")
    planned_reads = plan["files_to_read"]
    if (
        not planned_reads
        or len(planned_reads) != len(set(planned_reads))
        or any(path not in set(candidate_files) for path in planned_reads)
    ):
        raise ValueError("The approved plan contains an invalid file list.")
    understanding = approved_analysis.get("task_understanding")
    if not isinstance(understanding, dict) or not isinstance(
        understanding.get("likely_files"), list
    ):
        raise ValueError("The approved task understanding has invalid selected files.")
    if any(path not in set(candidate_files) for path in understanding["likely_files"]):
        raise ValueError("The task understanding selected an unavailable candidate file.")
    files_to_modify = [
        path for path in understanding["likely_files"] if path in set(planned_reads)
    ]
    files_to_create = requested_new_files
    if any(
        not isinstance(path, str)
        or path not in task
        or not path.startswith("sample_project/")
        or "\\" in path
        or ".." in path.split("/")
        or not path.endswith(".py")
        or path in set(current_files)
        for path in files_to_create
    ):
        raise ValueError(
            "A new file must be an exact sample_project/*.py path explicitly "
            "requested by the user and not already present."
        )
    if set(files_to_modify) & set(files_to_create):
        raise ValueError("A file cannot be both modified and created.")

    with temporary_project_copy() as temp_root:
        file_contents = {
            file_path: read_file(file_path, project_root=temp_root)
            for file_path in planned_reads
        }
        change_request = {
            "changes": [],
            "files_to_change": [],
            "explanation": "The approved plan did not require code changes.",
        }
        if files_to_modify or files_to_create:
            change_request = generate_change_request(
                task,
                plan,
                approved_analysis.get("rag_results", []),
                file_contents,
                files_to_modify,
                files_to_create,
            )
            apply_change_request(
                change_request,
                files_to_modify,
                temp_root,
                allowed_new_files=files_to_create,
            )

        test_result = run_tests(project_root=temp_root)
        test_attempts = [test_result]
        repair_attempted = False
        if not test_result["success"]:
            approved_files = files_to_modify + files_to_create
            if approved_files:
                repair_attempted = True
                current_contents = {
                    file_path: read_file(file_path, project_root=temp_root)
                    for file_path in approved_files
                }
                repair_request = repair_change_request(
                    task,
                    plan,
                    change_request,
                    test_result["output"],
                    current_contents,
                    approved_files,
                )
                apply_change_request(repair_request, approved_files, temp_root)
                test_result = run_tests(project_root=temp_root)
                test_attempts.append(test_result)
                change_request = {
                    "changes": change_request["changes"] + repair_request["changes"],
                    "files_to_change": list(
                        dict.fromkeys(
                            change_request["files_to_change"]
                            + repair_request["files_to_change"]
                        )
                    ),
                    "explanation": (
                        change_request["explanation"]
                        + "\nRepair: "
                        + repair_request["explanation"]
                    ),
                }

        diff_output = generate_diff(temp_root)

    summary_result = summarize_changes(
        task,
        change_request.get("explanation", ""),
        test_result,
        diff_output,
    )

    execution_result = None
    if test_result.get("success"):
        execution_result = _safe_run_generated_function(task, temp_root, change_request)

    return {
        **approved_analysis,
        "changes": change_request,
        "test_result": test_result,
        "test_attempts": test_attempts,
        "repair_attempted": repair_attempted,
        "diff": diff_output,
        "final_explanation": summary_result,
        "execution_result": execution_result,
    }
