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
    return {
        **approved_analysis,
        "changes": change_request,
        "test_result": test_result,
        "test_attempts": test_attempts,
        "repair_attempted": repair_attempted,
        "diff": diff_output,
        "final_explanation": summary_result,
    }
