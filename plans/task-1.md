# Task 1 Plan

## LLM provider

Qwen Code API on my VM via qwen-code-oai-proxy (OpenAI-compatible API).

## Model

qwen3-coder-plus

## Agent structure

1. Read the question from sys.argv[1]
2. Load .env.agent.secret
3. Read LLM_API_KEY, LLM_API_BASE, LLM_MODEL
4. Call OpenAI-compatible chat completions API
5. Extract assistant text
6. Print one JSON line to stdout:
   {"answer": "...", "tool_calls": []}
7. Print errors/debug info to stderr only

## Test strategy

Run agent.py as a subprocess, parse stdout as JSON, check that
answer and tool_calls exist, and that tool_calls is a list.
