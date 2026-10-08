# AI Coding Agent

A small AI coding assistant that takes a coding task in plain English, looks
through a sample Python project, creates a plan, and makes the required code
changes only after the user approves the plan.

I built this project to understand how an AI coding agent works in a simple,
practical way. The main focus is not on building a complicated AI system, but
on creating a complete flow from understanding a task to making, testing, and
showing a code change.

## What the project does:

The agent can:
- Take a coding task written in normal English.
- Look through the files in `sample_project/`.
- Find files that are likely related to the task using simple keyword-based
  retrieval.
- Use Google Gemini to understand the task and create an implementation plan.
- Show the plan before making any changes.
- Wait for the user to approve the plan.
- Generate small and focused code changes.
- Run the tests after making the changes.
- Show the actual code diff and explain what was changed.

## How it works

The overall flow is:

User Task
    ↓
Find Project Files
    ↓
Simple RAG
    ↓
Relevant Files
    ↓
Gemini Understands Task
    ↓
Gemini Creates Plan
    ↓
User Approves Plan
    ↓
Gemini Generates Code Change
    ↓
Apply Change
    ↓
Run Pytest
    ↓
Show Diff + Explanation