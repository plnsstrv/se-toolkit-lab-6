# AGENT.md

## Overview

This agent is a Python CLI program that takes one question from the command line,
sends it to an LLM through an OpenAI-compatible API, and returns one JSON line.

## Architecture

1. Read the question from `sys.argv[1]`
2. Load local `.env.agent.secret` for local development
3. Read `LLM_API_KEY`, `LLM_API_BASE`, and `LLM_MODEL` from environment variables
4. Create an OpenAI-compatible client
5. Send one chat completion request
6. Return JSON to stdout:
   {"answer": "...", "tool_calls": []}

## LLM provider

Qwen Code API on VM via qwen-code-oai-proxy

## Model

qwen3-coder-plus

## Output contract

- `answer` is required
- `tool_calls` is required
- `tool_calls` is an empty array in Task 1
- only valid JSON goes to stdout
- debug/errors go to stderr

## Local configuration

The agent can load local settings from `.env.agent.secret`.

Required variables:

- `LLM_API_KEY`
- `LLM_API_BASE`
- `LLM_MODEL`

## Testing

For testing without network access, set `AGENT_FAKE_ANSWER` environment variable:

```bash
AGENT_FAKE_ANSWER="Test answer" uv run agent.py "What is 2+2?"
```

## Run

```bash
uv run agent.py "What does REST stand for?"
uv run pytest
```
