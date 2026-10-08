import json
from pathlib import Path

import agent
import llm


TASK = "Add a function in routes.py that adds two numbers and add a test for it."
ROUTES = "sample_project/routes.py"
ROUTE_TESTS = "sample_project/tests/test_routes.py"
VALIDATORS = "sample_project/validators.py"
VALIDATOR_TESTS = "sample_project/tests/test_validators.py"


def _plan_response(files_to_read):
    return json.dumps(
        {
            "task": "Implement the requested change and validate it.",
            "files_to_read": files_to_read,
            "steps": ["Update the implementation and relevant test."],
        }
    )


def test_analyze_task_selects_related_routes_test(monkeypatch):
    monkeypatch.setattr(agent, "list_files", lambda: [ROUTES, ROUTE_TESTS, VALIDATORS, VALIDATOR_TESTS])
    prompts = []

    def get_plan(prompt):
        prompts.append(prompt)
        return _plan_response([ROUTES])

    monkeypatch.setattr(
        agent,
        "retrieve_relevant_code",
        lambda *args, **kwargs: [{"file_path": ROUTES, "similarity": 1.0}],
    )
    monkeypatch.setattr(
        agent,
        "understand_task",
        lambda *args, **kwargs: {
            "task_summary": TASK,
            "likely_files": [ROUTES],
            "reason": "The task targets routes.py.",
        },
    )
    monkeypatch.setattr(llm, "_call_gemini", get_plan)

    analysis = agent.analyze_task(TASK)

    assert analysis["plan"]["files_to_read"] == [ROUTES, ROUTE_TESTS]
    assert ROUTE_TESTS in analysis["candidate_files"]
    assert ROUTE_TESTS in analysis["task_understanding"]["likely_files"]
    normalized_prompt = " ".join(prompts[0].split())
    assert (
        "If the task asks to add or modify a test, include the relevant existing test "
        "file in files_to_read. Prefer an existing test file over creating a new test "
        "file when one already exists."
    ) in normalized_prompt


def test_plan_uses_validator_test_when_validator_task_requests_testing(monkeypatch):
    task = "Update validators.py and add a test."
    candidate_files = [VALIDATORS, VALIDATOR_TESTS, ROUTES, ROUTE_TESTS]
    monkeypatch.setattr(llm, "_call_gemini", lambda prompt: _plan_response([VALIDATORS]))

    plan = llm.create_plan(
        task,
        candidate_files,
        candidate_files,
        {path: "" for path in candidate_files},
        {"likely_files": [VALIDATORS]},
    )

    assert plan["files_to_read"] == [VALIDATORS, VALIDATOR_TESTS]


def test_plan_does_not_force_test_file_when_task_does_not_request_testing(monkeypatch):
    candidate_files = [ROUTES, ROUTE_TESTS, VALIDATORS, VALIDATOR_TESTS]
    monkeypatch.setattr(llm, "_call_gemini", lambda prompt: _plan_response([ROUTES]))

    plan = llm.create_plan(
        "Add a helper to routes.py.",
        candidate_files,
        candidate_files,
        {path: "" for path in candidate_files},
        {"likely_files": [ROUTES]},
    )

    assert plan["files_to_read"] == [ROUTES]


def test_approved_workflow_modifies_tests_runs_pytest_and_produces_diff(monkeypatch):
    available_files = agent.list_files()
    candidates = [ROUTES, ROUTE_TESTS]
    monkeypatch.setattr(agent, "list_files", lambda: available_files)
    monkeypatch.setattr(
        agent,
        "retrieve_relevant_code",
        lambda *args, **kwargs: [{"file_path": ROUTES, "similarity": 1.0}],
    )
    monkeypatch.setattr(
        agent,
        "understand_task",
        lambda *args, **kwargs: {
            "task_summary": TASK,
            "likely_files": [ROUTES],
            "reason": "The task targets routes.py.",
        },
    )
    monkeypatch.setattr(llm, "_call_gemini", lambda prompt: _plan_response([ROUTES]))
    analysis = agent.analyze_task(TASK)
    assert analysis["plan"]["files_to_read"] == candidates

    def generate_change_request(*args, **kwargs):
        source = Path(agent.__file__).parent / ROUTES
        source_text = source.read_text(encoding="utf-8")
        function_text = "def add_numbers(a, b):\n    return a + b"
        assert function_text in source_text
        return {
            "changes": [
                {
                    "file": ROUTES,
                    "operation": "modify",
                    "description": "Clarify the function implementation.",
                    "edits": [
                        {
                            "search": function_text,
                            "replace": 'def add_numbers(a, b):\n    """Return the sum of two values."""\n    return a + b',
                        }
                    ],
                },
                {
                    "file": ROUTE_TESTS,
                    "operation": "modify",
                    "description": "Add a test for the requested function.",
                    "edits": [
                        {
                            "search": "from sample_project.routes import register_user",
                            "replace": "from sample_project.routes import add_numbers, register_user",
                        },
                        {
                            "search": '        register_user("Alice", 30, "invalid-email-format")\n',
                            "replace": (
                                '        register_user("Alice", 30, "invalid-email-format")\n'
                                "\n\n"
                                "def test_add_numbers():\n"
                                "    assert add_numbers(10, 20) == 30\n"
                            ),
                        },
                    ],
                },
            ],
            "files_to_change": candidates,
            "explanation": "Updated the function and added its test.",
        }

    monkeypatch.setattr(agent, "generate_change_request", generate_change_request)
    monkeypatch.setattr(agent, "summarize_changes", lambda *args, **kwargs: "Completed.")

    result = agent.run_agent(analysis)

    assert result["test_result"]["success"] is True
    assert ROUTES in result["diff"]
    assert ROUTE_TESTS in result["diff"]
