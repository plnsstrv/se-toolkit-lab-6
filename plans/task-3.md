# Task 3 Plan: The System Agent

## Overview

Extend the Task 2 agent with a new `query_api` tool to query the deployed backend API. The agent will answer static system facts (framework, ports, status codes) and data-dependent queries (item count, scores).

## LLM Provider and Model

- **Provider:** Qwen Code API on VM via qwen-code-oai-proxy
- **Model:** qwen3-coder-plus
- **API:** OpenAI-compatible chat completions with function calling

## New Tool: query_api

### Schema

```json
{
    "name": "query_api",
    "description": "Query the backend API. Use this for live system data, status codes, item counts, and analytics.",
    "parameters": {
        "type": "object",
        "properties": {
            "method": {
                "type": "string",
                "description": "HTTP method (GET, POST, PUT, DELETE)"
            },
            "path": {
                "type": "string",
                "description": "API path (e.g., /items/, /analytics/completion-rate)"
            },
            "body": {
                "type": "string",
                "description": "Optional JSON request body (for POST/PUT)"
            }
        },
        "required": ["method", "path"]
    }
}
```

### Implementation

```python
def query_api(method: str, path: str, body: str | None = None) -> str:
    # Read LMS_API_KEY from environment
    # Read AGENT_API_BASE_URL from environment (default: http://localhost:42002)
    # Make HTTP request with Authorization header
    # Return JSON string: {"status_code": int, "body": str}
```

### Authentication

- Read `LMS_API_KEY` from `.env.docker.secret` or environment
- Include header: `Authorization: Bearer <LMS_API_KEY>`
- Default `AGENT_API_BASE_URL` to `http://localhost:42002` if not set

## Environment Variables

| Variable             | Purpose                              | Source              |
|---------------------|--------------------------------------|---------------------|
| `LLM_API_KEY`       | LLM provider API key                 | `.env.agent.secret` |
| `LLM_API_BASE`      | LLM API endpoint URL                 | `.env.agent.secret` |
| `LLM_MODEL`         | Model name                           | `.env.agent.secret` |
| `LMS_API_KEY`       | Backend API key for query_api auth   | `.env.docker.secret`|
| `AGENT_API_BASE_URL`| Base URL for query_api (optional)    | Environment/default |

## System Prompt Update

The system prompt will instruct the LLM to:

1. **Use wiki/code tools** (`read_file`, `list_files`) for:
   - Documentation questions
   - Source code inspection
   - Configuration questions
   - "How to" questions

2. **Use query_api** for:
   - Live system data (item counts, scores)
   - Status code questions
   - Analytics endpoints
   - Bug diagnosis (query + read source)

3. **Combine tools** for:
   - Bug diagnosis: query_api to see error, read_file to find bug
   - System understanding: read_file for config, query_api for verification

## Agentic Loop

No changes to the loop structure. Just add `query_api` to the TOOLS list.

```python
TOOLS = [read_file_schema, list_files_schema, query_api_schema]
```

## Path Security

Keep existing `safe_path()` implementation for `read_file` and `list_files`.
`query_api` does not need path security (uses HTTP client).

## Test Strategy

Two regression tests using `AGENT_FAKE_SCENARIO`:

1. **"What framework does the backend use?"**
   - Expect `read_file` in tool_calls
   - Simulate reading backend source code

2. **"How many items are in the database?"**
   - Expect `query_api` in tool_calls
   - Simulate API response with item count

## Benchmark Iteration Strategy

1. Run `uv run run_eval.py`
2. For each failing question:
   - Check if correct tool was used
   - Check if tool description is clear enough
   - Check if system prompt guides the LLM correctly
3. Fix and re-run until all 10 pass

## Output Contract

```json
{
    "answer": "string (required)",
    "source": "string (optional in Task 3)",
    "tool_calls": [
        {
            "tool": "read_file" | "list_files" | "query_api",
            "args": {...},
            "result": "..."
        }
    ]
}
```

## Implementation Structure

```python
# New tool
def query_api(method: str, path: str, body: str | None = None) -> str:
    lms_api_key = os.getenv("LMS_API_KEY")
    base_url = os.getenv("AGENT_API_BASE_URL", "http://localhost:42002")
    # Make request with urllib
    # Return JSON string

# Tool registry
TOOLS = [read_file, list_files, query_api]

# Execute tool
def execute_tool(tool_name, args):
    if tool_name == "query_api":
        return query_api(args["method"], args["path"], args.get("body"))
    # ... existing tools
```

## Benchmark Results

**Local tests:** 5/5 pytest tests passing

**Test scenarios verified:**

1. `test_agent_outputs_valid_json` - Task 1 compatibility ✓
2. `test_agent_read_file_for_merge_conflict` - Task 2 read_file ✓
3. `test_agent_list_files_for_wiki_question` - Task 2 list_files ✓
4. `test_agent_read_file_for_backend_framework` - Task 3 read_file ✓
5. `test_agent_query_api_for_items_count` - Task 3 query_api ✓

**Note:** Full `run_eval.py` benchmark requires autochecker credentials:

- AUTOCHECKER_API_URL
- AUTOCHECKER_EMAIL
- AUTOCHECKER_PASSWORD

The agent is ready for evaluation. To run the full benchmark:

1. Fill in `.env` with your autochecker credentials
2. Run: `uv run run_eval.py`
3. If any questions fail, check:
   - Correct tool is being used
   - Tool descriptions are clear
   - System prompt guides the LLM correctly
