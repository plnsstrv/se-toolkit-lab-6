"""
Regression tests for the Documentation Agent (Task 2).

These tests verify:
1. Valid JSON output with required fields (Task 1)
2. read_file tool usage for merge conflict question (Task 2)
3. list_files tool usage for wiki files question (Task 2)
"""

import json
import os
import subprocess
import sys


def test_agent_outputs_valid_json():
    """Test that agent outputs valid JSON with required fields (Task 1)."""
    env = os.environ.copy()
    env["LLM_API_KEY"] = "test-key"
    env["LLM_API_BASE"] = "http://example.invalid/v1"
    env["LLM_MODEL"] = "test-model"
    env["AGENT_FAKE_ANSWER"] = "Representational State Transfer."

    result = subprocess.run(
        [sys.executable, "agent.py", "What does REST stand for?"],
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr

    data = json.loads(result.stdout)

    assert "answer" in data
    assert "tool_calls" in data
    assert isinstance(data["tool_calls"], list)
    assert data["answer"] == "Representational State Transfer."


def test_agent_read_file_for_merge_conflict():
    """
    Test that agent uses read_file tool for merge conflict question (Task 2).
    
    Expectations:
    - read_file appears in tool_calls
    - source contains wiki/git-workflow.md
    """
    env = os.environ.copy()
    env["LLM_API_KEY"] = "test-key"
    env["LLM_API_BASE"] = "http://example.invalid/v1"
    env["LLM_MODEL"] = "test-model"
    env["AGENT_FAKE_SCENARIO"] = "merge_conflict"

    result = subprocess.run(
        [sys.executable, "agent.py", "How do you resolve a merge conflict?"],
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )

    assert result.returncode == 0, f"Agent failed: {result.stderr}"

    data = json.loads(result.stdout)

    # Check required fields
    assert "answer" in data, "Missing 'answer' field"
    assert "source" in data, "Missing 'source' field"
    assert "tool_calls" in data, "Missing 'tool_calls' field"
    assert isinstance(data["tool_calls"], list), "tool_calls must be a list"

    # Check that read_file was used
    tool_names = [tc.get("tool") for tc in data["tool_calls"]]
    assert "read_file" in tool_names, f"read_file not found in tool_calls: {tool_names}"

    # Check that source contains wiki/git-workflow.md
    assert "wiki/git-workflow.md" in data["source"], \
        f"Source should contain 'wiki/git-workflow.md', got: {data['source']}"


def test_agent_list_files_for_wiki_question():
    """
    Test that agent uses list_files tool for wiki files question (Task 2).
    
    Expectations:
    - list_files appears in tool_calls
    """
    env = os.environ.copy()
    env["LLM_API_KEY"] = "test-key"
    env["LLM_API_BASE"] = "http://example.invalid/v1"
    env["LLM_MODEL"] = "test-model"
    env["AGENT_FAKE_SCENARIO"] = "wiki_files"

    result = subprocess.run(
        [sys.executable, "agent.py", "What files are in the wiki?"],
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )

    assert result.returncode == 0, f"Agent failed: {result.stderr}"

    data = json.loads(result.stdout)

    # Check required fields
    assert "answer" in data, "Missing 'answer' field"
    assert "source" in data, "Missing 'source' field"
    assert "tool_calls" in data, "Missing 'tool_calls' field"
    assert isinstance(data["tool_calls"], list), "tool_calls must be a list"

    # Check that list_files was used
    tool_names = [tc.get("tool") for tc in data["tool_calls"]]
    assert "list_files" in tool_names, f"list_files not found in tool_calls: {tool_names}"
