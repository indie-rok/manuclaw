"""
registry.py
-----------
ToolRegistry: A central registry that lets you decorate plain Python functions
so they become LLM-callable tools.

Responsibilities
----------------
1. Store a reference to each registered function (keyed by name).
2. Store the JSON schema that describes each tool's parameters so it can be
   injected directly into an LLM's system prompt / tool list.
3. Expose a lightweight decorator API so tool authors never touch this file.

Usage
-----
    from registry import registry          # global singleton

    @registry.register(
        description="Send an email to a recipient",
        parameters={
            "type": "object",
            "properties": {
                "to":      {"type": "string", "description": "Recipient email"},
                "subject": {"type": "string", "description": "Email subject"},
                "body":    {"type": "string", "description": "Email body"},
            },
            "required": ["to", "subject", "body"],
        },
    )
    def send_email(to, subject, body):
        ...
"""

from __future__ import annotations

import functools
from typing import Any, Callable


class ToolRegistry:
    """
    A registry that maps tool names → (callable, JSON schema).

    The JSON schema follows the OpenAI / Anthropic function-calling spec so it
    can be forwarded to any modern LLM without transformation.
    """

    def __init__(self) -> None:
        # { tool_name: {"func": callable, "schema": dict} }
        self._tools: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(
        self,
        *,
        description: str,
        parameters: dict[str, Any],
        name: str | None = None,
    ) -> Callable:
        """
        Decorator factory that registers a function as an LLM tool.

        Parameters
        ----------
        description:
            Human-readable description sent to the LLM so it knows *when*
            to call this tool.
        parameters:
            JSON Schema object describing the tool's input.  Must follow the
            ``{"type": "object", "properties": {...}, "required": [...]}``
            convention expected by OpenAI/Anthropic tool-calling APIs.
        name:
            Override the tool name.  Defaults to the function's ``__name__``.

        Returns
        -------
        The original function, unchanged (decorator is transparent).
        """

        def decorator(func: Callable) -> Callable:
            tool_name = name or func.__name__

            if tool_name in self._tools:
                raise ValueError(
                    f"Tool '{tool_name}' is already registered. "
                    "Use a unique name or remove the duplicate."
                )

            self._tools[tool_name] = {
                "func": func,
                "schema": {
                    "name": tool_name,
                    "description": description,
                    "parameters": parameters,
                },
            }

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

            return wrapper

        return decorator

    def get_function(self, name: str) -> Callable:
        """
        Return the callable registered under *name*.

        Raises
        ------
        KeyError
            If no tool with that name has been registered.
        """
        entry = self._tools.get(name)
        if entry is None:
            raise KeyError(
                f"No tool named '{name}' found in registry. "
                f"Available tools: {list(self._tools.keys())}"
            )
        return entry["func"]

    def get_schema(self, name: str) -> dict[str, Any]:
        """Return the JSON schema for a single tool by name."""
        entry = self._tools.get(name)
        if entry is None:
            raise KeyError(f"No tool named '{name}' in registry.")
        return entry["schema"]

    def get_all_schemas(self) -> list[dict[str, Any]]:
        """
        Return all registered tool schemas as a list.

        This is the value you inject into the LLM's ``tools`` / ``functions``
        field at inference time.
        """
        return [entry["schema"] for entry in self._tools.values()]

    def list_tools(self) -> list[str]:
        """Return a sorted list of all registered tool names."""
        return sorted(self._tools.keys())

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __repr__(self) -> str:
        names = list(self._tools.keys())
        return f"<ToolRegistry tools={names}>"


# ---------------------------------------------------------------------------
# Module-level singleton — import this everywhere so there is a single source
# of truth for registered tools.
# ---------------------------------------------------------------------------
registry = ToolRegistry()
