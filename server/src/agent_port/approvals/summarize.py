import json


def summarize_tool_call(integration_id: str, tool_name: str, args: dict) -> str:
    pretty = json.dumps(args, indent=2)
    return f"Run {integration_id}.{tool_name} with arguments {pretty}"
