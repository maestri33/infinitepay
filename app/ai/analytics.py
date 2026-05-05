import json
import time

from app.ai.client import ai_enabled, get_client, get_model
from app.ai.tools import SYSTEM_PROMPT, TOOLS, execute_tool


def ask(question: str) -> dict:
    if not ai_enabled():
        return {"answer": "AI features desabilitadas.", "enabled": False}

    client = get_client()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    t0 = time.time()
    response = client.chat.completions.create(
        model=get_model(),
        messages=messages,
        tools=TOOLS,
        temperature=0.3,
    )
    msg = response.choices[0].message

    tool_calls_executed = []
    while msg.tool_calls:
        messages.append(msg)
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments) if tc.function.arguments else {}
            result = execute_tool(tc.function.name, args)
            tool_calls_executed.append({"tool": tc.function.name, "args": args})
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                }
            )

        response = client.chat.completions.create(
            model=get_model(),
            messages=messages,
            temperature=0.3,
        )
        msg = response.choices[0].message

    elapsed_ms = int((time.time() - t0) * 1000)

    return {
        "answer": msg.content or "(sem resposta)",
        "enabled": True,
        "model": get_model(),
        "elapsed_ms": elapsed_ms,
        "tools_called": tool_calls_executed,
        "usage": {
            "prompt_tokens": response.usage.prompt_tokens if response.usage else None,
            "completion_tokens": response.usage.completion_tokens if response.usage else None,
        },
    }
