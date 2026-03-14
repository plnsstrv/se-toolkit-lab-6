import json
import os
import sys

from dotenv import load_dotenv
from openai import OpenAI


def load_config() -> tuple[str, str, str]:
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


def call_llm(question: str, api_key: str, base_url: str, model: str) -> str:
    # Check for fake answer mode (for testing without network)
    fake_answer = os.getenv("AGENT_FAKE_ANSWER")
    if fake_answer:
        print(f"Using fake answer for testing: {fake_answer}", file=sys.stderr)
        return fake_answer

    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=55.0,
        max_retries=0,
    )

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": question}
        ],
    )

    answer = completion.choices[0].message.content

    if answer is None:
        return ""

    return answer.strip()


def main() -> int:
    if len(sys.argv) < 2:
        print('Usage: uv run agent.py "Your question here"', file=sys.stderr)
        return 1

    question = sys.argv[1]

    try:
        api_key, base_url, model = load_config()
        answer = call_llm(question, api_key, base_url, model)

        result = {
            "answer": answer,
            "tool_calls": [],
        }

        print(json.dumps(result, ensure_ascii=False))
        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())