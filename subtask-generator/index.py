import json
import os
from pathlib import Path
from typing import Dict, Any
import httpx
from dotenv import load_dotenv


class TaskBreaker:
    """
    Uses an LLM to generate subtasks based on:
    - User prompt
    - tools.json definitions
    """

    def __init__(
        self,
        tools_config_path: str = "tools.json",
        model: str = "openai/gpt-4o"
    ):
        load_dotenv()
        self.api_key = os.getenv("OPENROUTER_KEY")

        if not self.api_key:
            raise ValueError("OPENROUTER_KEY not found in environment variables")

        self.tools_path = Path(tools_config_path)
        self.tools_config = self._load_tools()
        self.model = model

    def _load_tools(self) -> Dict[str, Any]:
        if not self.tools_path.exists():
            raise FileNotFoundError(f"{self.tools_path} not found")

        with open(self.tools_path, "r") as f:
            return json.load(f)

    async def break_task(self, prompt: str) -> Dict[str, Any]:
        """
        Calls OpenRouter LLM to generate structured subtasks.
        """

        system_message = """
You are a task planning engine.

You receive:
1. A user prompt.
2. A JSON file describing available tools and execution flow.

Your job:
- Break the user prompt into clear, ordered subtasks.
- Assign exactly one tool per subtask.
- Use only tools defined in the provided JSON.
- Follow execution_flow logic when applicable.
- Return ONLY valid JSON.
- Do not explain anything.
Output format:
{
  "execution_plan": [
    {
      "step": int,
      "subtask_name": "string",
      "description": "string",
      "tool_to_use": "string",
      "reasoning": "short explanation"
    }
  ]
}
"""

        user_message = f"""
USER PROMPT:
{prompt}

TOOLS JSON:
{json.dumps(self.tools_config, indent=2)}
"""

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": user_message}
                    ],
                    "temperature": 0
                }
            )

        response.raise_for_status()
        data = response.json()

        content = data["choices"][0]["message"]["content"]

        # Ensure valid JSON parsing
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            raise ValueError("LLM did not return valid JSON.")