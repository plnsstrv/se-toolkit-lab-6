# AGENT.md

## Overview

This agent is a Python CLI program that answers questions by inspecting the project wiki using two tools: `read_file` and `list_files`. It implements an agentic loop that executes tool calls and feeds results back to the LLM.

## Architecture

1. Read the question from `sys.argv[1]`
2. Load configuration from `.env.agent.secret` (LLM_API_KEY, LLM_API_BASE, LLM_MODEL)
3. Send the question + tool definitions to the LLM
4. If the LLM returns tool calls:
   - Execute each tool (read_file or list_files)
   - Append results as tool role messages
   - Repeat (max 10 iterations)
5. If the LLM returns text (no tool calls) → final answer
6. Output JSON to stdout: `{answer, source, tool_calls}`

## LLM Provider

**Provider:** Qwen Code API on VM via qwen-code-oai-proxy (OpenAI-compatible API)

**Model:** qwen3-coder-plus

## Tools

### read_file

Read a file from the project repository.

**Schema:**

```json
{
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
```

**Security:**

- Rejects absolute paths
- Rejects `../` traversal
- Ensures resolved path is inside project root
- Returns error string if file doesn't exist

### list_files

List files and directories at a given path.

**Schema:**

```json
{
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
```

**Security:**

- Same path validation as read_file
- Returns newline-separated listing
- Returns error string if directory doesn't exist

## Agentic Loop

The agentic loop implements the following logic:

1. **Initialize messages** with system prompt and user question
2. **Loop** (max 10 iterations):
   - Call LLM with current messages + tool definitions
   - **If no tool calls:** Extract answer and return
   - **If tool calls present:**
     - Execute each tool
     - Record tool call (tool, args, result)
     - Append tool result as `tool` role message
     - Continue loop
3. **Max iterations reached:** Ask LLM for final answer based on gathered information

## System Prompt Strategy

The system prompt instructs the LLM to:

1. Use `list_files` first to discover wiki files
2. Use `read_file` to inspect relevant files
3. Answer using information from the wiki
4. Include source reference in format: `file_path#section_anchor`

Example source format:

- `wiki/git-workflow.md#resolving-merge-conflicts`
- `wiki/docker.md`

## Output Contract

```json
{
    "answer": "string (required) - The final answer to the question",
    "source": "string (required) - Wiki file reference (e.g., wiki/git-workflow.md#section)",
    "tool_calls": [
        {
            "tool": "read_file" | "list_files",
            "args": {"path": "..."},
            "result": "..."
        }
    ]
}
```

**Rules:**

- Only valid JSON goes to stdout
- All debug/progress output goes to stderr
- Exit code 0 on success

## Local Configuration

The agent loads settings from `.env.agent.secret`.

**Required variables:**

- `LLM_API_KEY` - API key for LLM provider
- `LLM_API_BASE` - Base URL for OpenAI-compatible API
- `LLM_MODEL` - Model name (e.g., qwen3-coder-plus)

## Testing

For testing without network access, set `AGENT_FAKE_SCENARIO` environment variable:

```bash
# Simulate merge conflict scenario
AGENT_FAKE_SCENARIO=merge_conflict uv run agent.py "How do you resolve a merge conflict?"

# Simulate wiki files scenario
AGENT_FAKE_SCENARIO=wiki_files uv run agent.py "What files are in the wiki?"
```

**Available scenarios:**

- `merge_conflict` - Returns fake tool calls for git-workflow.md
- `wiki_files` - Returns fake tool calls for list_files on wiki/

## Run

```bash
uv run agent.py "How do you resolve a merge conflict?"
uv run pytest
```

## Path Security

The agent implements strict path validation:

1. Reject absolute paths
2. Reject `../` traversal patterns
3. Resolve path against project root
4. Verify resolved path is still inside project root

This prevents directory traversal attacks and ensures the agent only accesses project files.
