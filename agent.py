#!/usr/bin/env python3
"""
Documentation Agent - Task 2

A CLI agent that uses read_file and list_files tools to answer questions
by inspecting the project wiki.
"""

import json
import os
import sys
from pathlib import Path

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


# Tool schemas for OpenAI function calling
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the project repository. Use this to inspect file contents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path from project root (e.g., 'wiki/git-workflow.md')"
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
            "description": "List files and directories at a given path. Use this to discover what files exist.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative directory path from project root (e.g., 'wiki')"
                    }
                },
                "required": ["path"]
            }
        }
    }
]

# System prompt for the documentation agent
SYSTEM_PROMPT = """You are a documentation assistant that answers questions using the project wiki.

You have access to two tools:
1. list_files - List files and directories at a given path
2. read_file - Read the contents of a file

Strategy:
1. First use list_files to discover what wiki files exist
2. Then use read_file to inspect relevant files
3. Answer the question using information from the wiki
4. Always include a source reference in your answer

When you mention information from a file, include the source in this format:
- File path: wiki/filename.md
- Section anchor: wiki/filename.md#section-name (use lowercase with hyphens)

For example: wiki/git-workflow.md#resolving-merge-conflicts

Be concise and accurate. Only use information from the wiki files."""


def execute_tool(tool_name: str, args: dict) -> str:
    """Execute a tool and return the result."""
    if tool_name == "read_file":
        path = args.get("path", "")
        return read_file(path)
    elif tool_name == "list_files":
        path = args.get("path", "")
        return list_files(path)
    else:
        return f"Error: Unknown tool: {tool_name}"


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
    
    # Check for fake scenario mode (Task 2 - tool calling simulation)
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
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
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
    - wiki/filename.md#section-name
    """
    import re
    
    # Try to find wiki file reference in answer
    wiki_pattern = r'(wiki/[\w\-]+\.md(?:#[\w\-]+)?)'
    matches = re.findall(wiki_pattern, answer)
    
    if matches:
        return matches[0]
    
    # If we have a last read file, use it as source
    if last_read_file_path:
        return last_read_file_path
    
    # Default fallback
    return "wiki"


def get_fake_scenario_result(scenario: str, question: str) -> dict:
    """
    Return fake results for testing without network access.
    
    Scenarios:
    - merge_conflict: simulate read_file for git-workflow.md
    - wiki_files: simulate list_files for wiki directory
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
    else:
        # Generic fallback
        return {
            "answer": f"Answer to: {question}",
            "source": "wiki",
            "tool_calls": []
        }


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
