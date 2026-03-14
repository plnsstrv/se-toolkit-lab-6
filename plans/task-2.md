# Task 2 Plan: The Documentation Agent

## Overview

Upgrade the Task 1 agent to support tool calling with two tools: `read_file` and `list_files`. Implement an agentic loop that executes tool calls and feeds results back to the LLM.

## LLM Provider and Model

- **Provider:** Qwen Code API on VM via qwen-code-oai-proxy
- **Model:** qwen3-coder-plus
- **API:** OpenAI-compatible chat completions with function calling

## Tool Schemas

### read_file

```python
{
    "name": "read_file",
    "description": "Read a file from the project repository",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative path from project root"}
        },
        "required": ["path"]
    }
}
```

**Security:**
- Resolve path against project root
- Reject `../` traversal
- Ensure resolved path is inside project directory
- Return error string if file doesn't exist

### list_files

```python
{
    "name": "list_files",
    "description": "List files and directories at a given path",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative directory path from project root"}
        },
        "required": ["path"]
    }
}
```

**Security:**
- Same path validation as read_file
- Return newline-separated listing
- Return error string if directory doesn't exist

## Agentic Loop

1. Send user question + tool definitions to LLM
2. Parse response:
   - If `tool_calls` present:
     - Execute each tool
     - Append results as `tool` role messages
     - Repeat (max 10 iterations)
   - If no `tool_calls`:
     - Extract answer from assistant message
     - Extract source from answer (or infer from last read_file)
3. Output JSON: `{answer, source, tool_calls}`

## System Prompt Strategy

The system prompt will instruct the LLM to:
1. Use `list_files` first to discover wiki files
2. Use `read_file` to inspect relevant files
3. Answer using information from the wiki
4. Include source reference in format: `file_path#section_anchor`

## Path Security Implementation

```python
def safe_path(project_root: Path, relative_path: str) -> Path:
    # Reject absolute paths
    # Reject ../ traversal
    # Resolve against project root
    # Verify resolved path is still inside project root
```

## Output Contract

```json
{
    "answer": "string (required)",
    "source": "string (required, e.g., wiki/git-workflow.md#resolving-merge-conflicts)",
    "tool_calls": [
        {
            "tool": "read_file" | "list_files",
            "args": {"path": "..."},
            "result": "..."
        }
    ]
}
```

## Test Strategy

Two regression tests using `AGENT_FAKE_SCENARIO` hook:

1. **"How do you resolve a merge conflict?"**
   - Expect `read_file` in tool_calls
   - Expect `wiki/git-workflow.md` in source

2. **"What files are in the wiki?"**
   - Expect `list_files` in tool_calls

Tests will use environment variable to simulate tool-calling flow without real LLM.

## Implementation Structure

```python
# Tools
def read_file(path: str) -> str
def list_files(path: str) -> str

# Tool registry
TOOLS = [...]  # OpenAI function schemas

# Agentic loop
def run_agent_loop(question: str, api_key, base_url, model) -> dict:
    messages = [system_prompt, user_question]
    tool_calls = []
    
    for _ in range(MAX_TOOL_CALLS):
        response = client.chat.completions.create(...)
        
        if no tool_calls:
            break
        
        for tool_call in response.tool_calls:
            execute tool
            append result to messages
            record in tool_calls list
    
    return {answer, source, tool_calls}
```
