import json
import os
import subprocess
import sys


def test_agent_outputs_valid_json():
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
