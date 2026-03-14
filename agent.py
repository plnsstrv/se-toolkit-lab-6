#!/usr/bin/env python3
"""
System Agent - Task 3

A CLI agent that uses read_file, list_files, and query_api tools to answer questions
by inspecting the project wiki, source code, and querying the backend API.
"""

import json
import os
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from dotenv import load_dotenv
from openai import OpenAI

# Maximum number of tool calls per question
MAX_TOOL_CALLS = 10

# Project root for path security
PROJECT_ROOT = Path(__file__).parent.resolve()


def load_config() -> tuple[str, str, str]:
    """Load LLM configuration from environment variables."""
    load_dotenv(".env.agent.secret")

    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_API_BASE")
    model = os.getenv("LLM_MODEL")

    if not api_key:
        raise RuntimeError("LLM_API_KEY is missing in .env.agent.secret")
    if not base_url:
        raise RuntimeError("LLM_API_BASE is missing in .env.agent.secret")
    if not model:
        raise RuntimeError("LLM_MODEL is missing in .env.agent.secret")

    return api_key, base_url, model


def safe_path(relative_path: str) -> Path:
    """
    Resolve a relative path against project root and ensure it stays inside.

    Security: rejects ../ traversal and absolute paths outside project.
    """
    # Reject absolute paths
    if Path(relative_path).is_absolute():
        raise ValueError(f"Absolute paths not allowed: {relative_path}")

    # Reject obvious traversal attempts
    if ".." in relative_path.split("/") or ".." in relative_path.split(os.sep):
        raise ValueError(f"Path traversal not allowed: {relative_path}")

    # Resolve against project root
    resolved = (PROJECT_ROOT / relative_path).resolve()

    # Ensure resolved path is inside project root
    try:
        resolved.relative_to(PROJECT_ROOT)
    except ValueError:
        raise ValueError(f"Path escapes project root: {relative_path}")

    return resolved


def read_file(path: str) -> str:
    """
    Read a file from the project repository.

    Args:
        path: Relative path from project root

    Returns:
        File contents as string, or error message
    """
    try:
        safe = safe_path(path)
        if not safe.exists():
            return f"Error: File not found: {path}"
        if not safe.is_file():
            return f"Error: Not a file: {path}"
        return safe.read_text(encoding="utf-8")
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error reading file: {e}"


def list_files(path: str) -> str:
    """
    List files and directories at a given path.

    Args:
        path: Relative directory path from project root

    Returns:
        Newline-separated listing, or error message
    """
    try:
        safe = safe_path(path)
        if not safe.exists():
            return f"Error: Directory not found: {path}"
        if not safe.is_dir():
            return f"Error: Not a directory: {path}"

        entries = []
        for entry in sorted(safe.iterdir()):
            suffix = "/" if entry.is_dir() else ""
            entries.append(f"{entry.name}{suffix}")
        return "\n".join(entries)
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error listing directory: {e}"


def query_api(method: str, path: str, body: str | None = None) -> str:
    """
    Query the backend API.

    Args:
        method: HTTP method (GET, POST, PUT, DELETE)
        path: API path (e.g., /items/, /analytics/completion-rate)
        body: Optional JSON request body (for POST/PUT)

    Returns:
        JSON string with status_code and body
    """
    # Load backend config
    load_dotenv(".env.docker.secret")

    lms_api_key = os.getenv("LMS_API_KEY")
    base_url = os.getenv("AGENT_API_BASE_URL", "http://localhost:42002")

    if not lms_api_key:
        return json.dumps({
            "status_code": 0,
            "body": "Error: LMS_API_KEY is not configured"
        })

    # Build URL
    url = f"{base_url.rstrip('/')}{path}"

    # Prepare headers
    headers = {
        "Authorization": f"Bearer {lms_api_key}",
        "Content-Type": "application/json"
    }

    try:
        # Prepare request body
        data = None
        if body and method.upper() in ("POST", "PUT", "PATCH"):
            data = body.encode("utf-8")

        # Make request
        req = Request(url, data=data, headers=headers, method=method.upper())

        try:
            with urlopen(req, timeout=30) as response:
                response_body = response.read().decode("utf-8")
                return json.dumps({
                    "status_code": response.status,
                    "body": response_body
                })
        except HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            return json.dumps({
                "status_code": e.code,
                "body": error_body
            })
        except URLError as e:
            return json.dumps({
                "status_code": 0,
                "body": f"Error: Cannot connect to API: {e.reason}"
            })

    except Exception as e:
        return json.dumps({
            "status_code": 0,
            "body": f"Error: {str(e)}"
        })


# Tool schemas for OpenAI function calling
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the project repository. Use this to inspect source code, documentation, or configuration files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path from project root (e.g., 'wiki/git-workflow.md', 'backend/app/main.py')"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories at a given path. Use this to discover what files exist in a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative directory path from project root (e.g., 'wiki', 'backend/app/routers')"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_api",
            "description": "Query the backend API. Use this for live system data, item counts, status codes, analytics endpoints, or bug diagnosis.",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "description": "HTTP method (GET, POST, PUT, DELETE)"
                    },
                    "path": {
                        "type": "string",
                        "description": "API path (e.g., /items/, /analytics/completion-rate, /analytics/top-learners)"
                    },
                    "body": {
                        "type": "string",
                        "description": "Optional JSON request body for POST/PUT requests"
                    }
                },
                "required": ["method", "path"]
            }
        }
    }
]

# System prompt for the system agent
SYSTEM_PROMPT = """You are a system assistant that answers questions using the project wiki, source code, and backend API.

You have access to three tools:
1. list_files - List files and directories at a given path
2. read_file - Read the contents of a file (source code, docs, config)
3. query_api - Query the backend API for live data

Tool selection strategy:
- Use list_files to discover what files exist in a directory
- Use read_file to inspect source code, documentation, or configuration
- Use query_api for live system data, item counts, status codes, analytics

When to use each tool:
- Wiki/documentation questions → read_file (e.g., wiki/git-workflow.md)
- Source code questions → read_file (e.g., backend/app/main.py)
- "What framework does it use?" → read_file on source code
- "How many items..." → query_api GET /items/
- "What status code..." → query_api (make the request)
- Bug diagnosis → query_api first to see the error, then read_file to find the bug
- System architecture → read_file on docker-compose.yml, Dockerfile, config files

When you mention information from a file, include the source in this format:
- File path: wiki/filename.md or backend/app/file.py
- Section anchor: wiki/filename.md#section-name (use lowercase with hyphens)

Be concise and accurate. Use the right tool for each question."""


def execute_tool(tool_name: str, args: dict) -> str:
    """Execute a tool and return the result."""
    if tool_name == "read_file":
        path = args.get("path", "")
        return read_file(path)
    elif tool_name == "list_files":
        path = args.get("path", "")
        return list_files(path)
    elif tool_name == "query_api":
        method = args.get("method", "GET")
        path = args.get("path", "")
        body = args.get("body")
        return query_api(method, path, body)
    else:
        return f"Error: Unknown tool: {tool_name}"


def get_fake_scenario_result(scenario: str, question: str) -> dict:
    """
    Return fake results for testing without network access.

    Scenarios:
    - merge_conflict: simulate read_file for git-workflow.md
    - wiki_files: simulate list_files for wiki directory
    - backend_framework: simulate read_file for backend source
    - items_count: simulate query_api for /items/
    """
    if scenario == "merge_conflict":
        return {
            "answer": "To resolve a merge conflict, open the conflicting file, look for conflict markers (<<<<<<, ======, >>>>>>), edit to keep the desired changes, remove the markers, then stage and commit.",
            "source": "wiki/git-workflow.md#resolving-merge-conflicts",
            "tool_calls": [
                {
                    "tool": "list_files",
                    "args": {"path": "wiki"},
                    "result": "git-workflow.md\nREADME.md\n"
                },
                {
                    "tool": "read_file",
                    "args": {"path": "wiki/git-workflow.md"},
                    "result": "# Git Workflow\n\n## Resolving Merge Conflicts\n\nWhen you have a merge conflict, edit the file to choose which changes to keep."
                }
            ]
        }
    elif scenario == "wiki_files":
        return {
            "answer": "The wiki contains documentation files including: git-workflow.md, README.md, python.md, docker.md, and many more.",
            "source": "wiki",
            "tool_calls": [
                {
                    "tool": "list_files",
                    "args": {"path": "wiki"},
                    "result": "git-workflow.md\nREADME.md\npython.md\ndocker.md\n"
                }
            ]
        }
    elif scenario == "backend_framework":
        return {
            "answer": "The backend uses the FastAPI framework, which is a modern Python web framework for building APIs.",
            "source": "backend/app/main.py",
            "tool_calls": [
                {
                    "tool": "read_file",
                    "args": {"path": "backend/app/main.py"},
                    "result": "from fastapi import FastAPI\n\napp = FastAPI(title='Learning Management Service')"
                }
            ]
        }
    elif scenario == "items_count":
        return {
            "answer": "There are 42 items currently stored in the database.",
            "source": "",
            "tool_calls": [
                {
                    "tool": "query_api",
                    "args": {"method": "GET", "path": "/items/"},
                    "result": '{"status_code": 200, "body": "[{\"id\": 1}, ... 42 items]"}'
                }
            ]
        }
    else:
        # Generic fallback
        return {
            "answer": f"Answer to: {question}",
            "source": "wiki",
            "tool_calls": []
        }


def run_agent_loop(
    question: str,
    api_key: str,
    base_url: str,
    model: str
) -> dict:
    """
    Run the agentic loop: send question to LLM, execute tool calls, return answer.

    Returns:
        dict with answer, source, and tool_calls
    """
    # Check for fake answer mode (Task 1 compatibility - simple text answer)
    fake_answer = os.getenv("AGENT_FAKE_ANSWER")
    if fake_answer:
        print(f"Using fake answer for testing: {fake_answer}", file=sys.stderr)
        return {
            "answer": fake_answer,
            "source": "wiki",
            "tool_calls": []
        }

    # Check for fake scenario mode (Task 2/3 - tool calling simulation)
    fake_scenario = os.getenv("AGENT_FAKE_SCENARIO")
    if fake_scenario:
        print(f"Using fake scenario for testing: {fake_scenario}", file=sys.stderr)
        return get_fake_scenario_result(fake_scenario, question)

    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=55.0,
        max_retries=0,
    )

    # Initialize messages with system prompt and user question
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question}
    ]

    # Track all tool calls for output
    all_tool_calls = []
    last_read_file_path = None

    # Agentic loop
    for iteration in range(MAX_TOOL_CALLS):
        print(f"Agentic loop iteration {iteration + 1}/{MAX_TOOL_CALLS}", file=sys.stderr)

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )

        choice = response.choices[0]
        assistant_message = choice.message

        # Check for tool calls
        tool_calls = assistant_message.tool_calls

        if not tool_calls:
            # No tool calls - this is the final answer
            # Safely handle content being None
            answer = assistant_message.content or ""
            source = extract_source(answer, last_read_file_path)
            return {
                "answer": answer.strip(),
                "source": source,
                "tool_calls": all_tool_calls
            }

        # Execute tool calls
        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)

            print(f"Executing tool: {tool_name}({tool_args})", file=sys.stderr)

            # Execute the tool
            result = execute_tool(tool_name, tool_args)

            # Record the tool call
            tool_call_record = {
                "tool": tool_name,
                "args": tool_args,
                "result": result
            }
            all_tool_calls.append(tool_call_record)

            # Track last read_file for source extraction
            if tool_name == "read_file":
                last_read_file_path = tool_args.get("path", "")

            # Append tool result to messages
            # Safely handle tool_call.id being None
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id or f"{tool_name}_{len(all_tool_calls)}",
                "content": result
            })

    # Max iterations reached - use whatever we have
    print("Max tool calls reached, generating final answer", file=sys.stderr)

    # Ask LLM for final answer based on collected information
    messages.append({
        "role": "system",
        "content": "You have reached the maximum number of tool calls. Please provide your final answer based on the information you have gathered."
    })

    response = client.chat.completions.create(
        model=model,
        messages=messages,
    )

    # Safely handle content being None
    answer = response.choices[0].message.content or ""
    source = extract_source(answer, last_read_file_path)

    return {
        "answer": answer.strip(),
        "source": source,
        "tool_calls": all_tool_calls
    }


def extract_source(answer: str, last_read_file_path: str | None) -> str:
    """
    Extract source reference from answer or infer from last read file.

    Looks for patterns like:
    - wiki/filename.md
    - wiki/filename.md#section
    - backend/app/file.py
    """
    import re

    # Try to find wiki file reference in answer
    wiki_pattern = r'(wiki/[\w\-]+\.md(?:#[\w\-]+)?)'
    matches = re.findall(wiki_pattern, answer)

    if matches:
        return matches[0]

    # Try to find backend file reference
    backend_pattern = r'(backend/[\w\-]+\.py)'
    backend_matches = re.findall(backend_pattern, answer)

    if backend_matches:
        return backend_matches[0]

    # If we have a last read file, use it as source
    if last_read_file_path:
        return last_read_file_path

    # Default fallback - empty string for system questions
    return ""


def main() -> int:
    """Main entry point."""
    if len(sys.argv) < 2:
        print('Usage: uv run agent.py "Your question here"', file=sys.stderr)
        return 1

    question = sys.argv[1]

    try:
        api_key, base_url, model = load_config()
        result = run_agent_loop(question, api_key, base_url, model)

        # Output exactly one JSON line to stdout
        print(json.dumps(result, ensure_ascii=False))
        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
