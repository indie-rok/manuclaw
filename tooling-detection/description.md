System Role: Act as a Senior Backend Engineer specializing in Agentic Frameworks.

Task: Build a Python-based Tool Execution Module specifically for a "Send Email" tool. The module must be compatible with an LLM's tool-calling output. Code should be inside the tooling-detection directory

Requirements:

The Registry: Create a ToolRegistry class that can register functions via decorators and store their JSON schemas for LLM context.

The Email Tool: Implement a send_email(to: str, subject: str, body: str) function. Use smtplib for the implementation or a placeholder for a service like SendGrid/Resend.

The Dispatcher: Create an execute_tool(call_json) function. It should:

Parse the LLM's JSON output.

Validate the parameters using Pydantic.

Execute the function and catch any exceptions (SMTP errors, auth errors).

The Observation Loop: Ensure the function returns a stringified result that the LLM can understand (e.g., "Success: Email sent to X" or "Error: Authentication failed").

Security: Ensure sensitive credentials (SMTP passwords) are pulled from environment variables, not hardcoded.

Output Style: Provide modular, well-documented code with a clear separation between the tool logic and the execution engine.