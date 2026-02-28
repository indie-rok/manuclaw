"""
tools/
------
Each module in this sub-package implements one or more LLM-callable tools
and registers them against the global ToolRegistry singleton.

Importing this package triggers all registrations automatically.
"""

from tools.email_tool import send_email  # noqa: F401 – side-effect: registers tool
