# AGENT.md

## Overview

This agent is a Python CLI program that answers questions by inspecting the project wiki, source code, and querying the backend API. It implements an agentic loop that executes tool calls and feeds results back to the LLM.

## Architecture

1. Read the question from `sys.argv[1]`
2. Load configuration from `.env.agent.secret` (LLM_API_KEY, LLM_API_BASE, LLM_MODEL)
3. Send the question + tool definitions to the LLM
4. If the LLM returns tool calls:
   - Execute each tool (read_file, list_files, or query_api)
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
```

**Security:**

- Same path validation as read_file
- Returns newline-separated listing
- Returns error string if directory doesn't exist

### query_api

Query the backend API for live data.

**Schema:**

```json
{
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
```

**Authentication:**

- Reads `LMS_API_KEY` from `.env.docker.secret` or environment
- Includes header: `Authorization: Bearer <LMS_API_KEY>`
- Default `AGENT_API_BASE_URL` is `http://localhost:42002` (Caddy proxy)

**Returns:**

- JSON string: `{"status_code": int, "body": string}`

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

1. Use `list_files` to discover wiki files
2. Use `read_file` to inspect relevant files
3. Use `query_api` for live system data
4. Include source reference in format: `file_path#section_anchor`

**Tool selection guidance:**

- Wiki/documentation questions → `read_file` (e.g., wiki/git-workflow.md)
- Source code questions → `read_file` (e.g., backend/app/main.py)
- "What framework does it use?" → `read_file` on source code
- "How many items..." → `query_api` GET /items/
- "What status code..." → `query_api` (make the request)
- Bug diagnosis → `query_api` first to see the error, then `read_file` to find the bug
- System architecture → `read_file` on docker-compose.yml, Dockerfile, config files

## Output Contract

```json
{
    "answer": "string (required) - The final answer to the question",
    "source": "string (optional) - Wiki file reference (e.g., wiki/git-workflow.md#section)",
    "tool_calls": [
        {
            "tool": "read_file" | "list_files" | "query_api",
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

The agent loads settings from environment variables:

**LLM configuration (`.env.agent.secret`):**

- `LLM_API_KEY` - API key for LLM provider
- `LLM_API_BASE` - Base URL for OpenAI-compatible API
- `LLM_MODEL` - Model name (e.g., qwen3-coder-plus)

**Backend configuration (`.env.docker.secret`):**

- `LMS_API_KEY` - API key for backend authentication
- `AGENT_API_BASE_URL` - Base URL for query_api (default: <http://localhost:42002>)

## Testing

For testing without network access, set `AGENT_FAKE_SCENARIO` environment variable:

```bash
# Simulate merge conflict scenario
AGENT_FAKE_SCENARIO=merge_conflict uv run agent.py "How do you resolve a merge conflict?"

# Simulate backend framework scenario
AGENT_FAKE_SCENARIO=backend_framework uv run agent.py "What framework does the backend use?"

# Simulate items count scenario
AGENT_FAKE_SCENARIO=items_count uv run agent.py "How many items are in the database?"
```

**Available scenarios:**

- `merge_conflict` - Returns fake tool calls for git-workflow.md
- `wiki_files` - Returns fake tool calls for list_files on wiki/
- `backend_framework` - Returns fake tool calls for backend source
- `items_count` - Returns fake tool calls for query_api /items/

## Run

```bash
uv run agent.py "How do you resolve a merge conflict?"
uv run pytest
uv run run_eval.py
```

## Path Security

The agent implements strict path validation:

1. Reject absolute paths
2. Reject `../` traversal patterns
3. Resolve path against project root
4. Verify resolved path is still inside project root

This prevents directory traversal attacks and ensures the agent only accesses project files.

## Lessons Learned

1. **Tool descriptions matter:** Initially the LLM would call the wrong tool. Making descriptions more specific (e.g., "Use query_api for live system data, item counts, status codes") improved tool selection significantly.

2. **Handle null content safely:** The LLM may return `content: null` when making tool calls. Using `(content or "")` instead of `content` prevents AttributeError crashes.

3. **System prompt balance:** Too much detail confuses the LLM; too little leads to wrong tool usage. The sweet spot is clear examples of when to use each tool.

4. **Authentication separation:** Keeping `LMS_API_KEY` (backend) separate from `LLM_API_KEY` (LLM provider) is crucial. They serve different purposes and come from different files.

5. **Max iterations:** 10 tool calls is usually enough. Most questions require 2-4 tool calls. Setting a limit prevents infinite loops.

6. **Source extraction:** Using regex to extract file references from the answer works better than relying solely on the LLM to format it correctly.

## Benchmark Results

Final score: **10/10** on local evaluation with `run_eval.py`.

The agent successfully:

- Uses `read_file` for wiki and source code questions
- Uses `list_files` to discover API router modules
- Uses `query_api` for live data and status code questions
- Combines `query_api` + `read_file` for bug diagnosis questions
- Traces the full HTTP request path for architecture questions
- Explains ETL idempotency using external_id duplicate skipping
