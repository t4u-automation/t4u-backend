"""E2B Selenium Tool - Persistent Selenium WebDriver server in E2B"""

import json
import time
from pathlib import Path
from typing import Optional

from pydantic import PrivateAttr

from app.config import PROJECT_ROOT
from app.e2b.tool_base import E2BToolsBase
from app.tool.base import ToolResult
from app.utils.logger import logger

_SELENIUM_DESCRIPTION = """\
Experimental web automation tool using Selenium WebDriver.
Alternative to Playwright for web navigation and interaction.

Features:
- Navigate to URLs
- Click elements
- Fill forms
- Extract page content
- Take screenshots

Runs in E2B sandbox with ChromeDriver.
"""


class E2BSeleniumTool(E2BToolsBase):
    """
    Selenium-based web automation tool running in E2B sandbox.
    Uses persistent WebDriver server (like Playwright) for stateful browsing.
    """

    name: str = "e2b_selenium"
    description: str = _SELENIUM_DESCRIPTION

    # Persistent Selenium server management
    _selenium_script_path: str = PrivateAttr(default="/tmp/selenium_server.py")
    _selenium_pid_file: str = PrivateAttr(default="/tmp/selenium.pid")
    _selenium_initialized: bool = PrivateAttr(default=False)

    parameters: dict = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "navigate",
                    "click",
                    "input_text",
                    "get_page_info",
                    "take_screenshot",
                    "go_back",
                    "go_forward",
                    "refresh",
                ],
                "description": "Action to perform",
            },
            "url": {
                "type": "string",
                "description": "URL to navigate to (for navigate action)",
            },
            "selector": {
                "type": "string",
                "description": "CSS selector or XPath for element (for click/input actions)",
            },
            "text": {
                "type": "string",
                "description": "Text to input (for input_text action)",
            },
            "file_path": {
                "type": "string",
                "description": "Path to save screenshot (for take_screenshot action)",
            },
        },
        "required": ["action"],
    }

    async def _ensure_selenium_server(self):
        """Ensure persistent Selenium server is running in E2B"""
        if not self.sandbox:
            raise ValueError("E2B sandbox not initialized")

        if self._selenium_initialized:
            # Check if still running
            check = self.sandbox.exec(
                f"test -f {self._selenium_pid_file} && kill -0 $(cat {self._selenium_pid_file}) 2>/dev/null && echo 'running' || echo 'stopped'"
            )
            if "running" in check.stdout:
                return  # Server is running

        logger.info("Starting persistent Selenium server...")

        # Read selenium_server.py from project root
        server_script_path = PROJECT_ROOT / "selenium_server.py"
        if server_script_path.exists():
            with open(server_script_path, "r") as f:
                server_script = f.read()
        else:
            return self.fail_response("selenium_server.py not found in project root")

        # Upload to E2B
        self.sandbox.filesystem_write(self._selenium_script_path, server_script)

        # Start server in background
        start_cmd = f"cd /home/user && nohup python3 {self._selenium_script_path} > /tmp/selenium.log 2>&1 & echo $! > {self._selenium_pid_file}"
        self.sandbox.exec(start_cmd)

        # Wait for server to be ready
        max_wait = 30
        for i in range(max_wait):
            check = self.sandbox.exec(
                f"grep -q 'Selenium server ready' /tmp/selenium.log && echo 'ready' || echo 'not ready'"
            )
            if "ready" in check.stdout:
                logger.info(f"Selenium server ready after {i+1}s")
                self._selenium_initialized = True
                return
            time.sleep(1)

        raise TimeoutError("Selenium server failed to start within 30 seconds")

    async def _execute_selenium_command(self, command: dict) -> dict:
        """Execute command on persistent Selenium server via JSON files"""
        import time as time_module
        start_time = time_module.time()
        
        # Write command
        command_json = json.dumps(command)
        logger.debug(f"📝 Writing command to /tmp/selenium_command.json: {command.get('action')}")
        write_start = time_module.time()
        self.sandbox.filesystem_write("/tmp/selenium_command.json", command_json)
        write_elapsed = time_module.time() - write_start
        logger.debug(f"⏱️  Command write took: {write_elapsed:.2f}s")

        # Wait for response (with timeout)
        max_wait = 60
        poll_start = time_module.time()
        logger.debug(f"⏳ Starting to poll for response (max {max_wait}s)...")
        
        for i in range(max_wait * 2):  # Check every 0.5s
            try:
                response_data = self.sandbox.filesystem_read(
                    "/tmp/selenium_response.json"
                )
                if response_data:
                    poll_elapsed = time_module.time() - poll_start
                    logger.debug(f"✅ Response received after {poll_elapsed:.2f}s (poll attempt {i+1})")
                    
                    # Remove response file
                    rm_start = time_module.time()
                    self.sandbox.exec("rm -f /tmp/selenium_response.json")
                    rm_elapsed = time_module.time() - rm_start
                    logger.debug(f"⏱️  Response file removal took: {rm_elapsed:.2f}s")
                    
                    # Parse JSON
                    parse_start = time_module.time()
                    result = json.loads(response_data)
                    parse_elapsed = time_module.time() - parse_start
                    logger.debug(f"⏱️  JSON parsing took: {parse_elapsed:.2f}s")
                    
                    total_elapsed = time_module.time() - start_time
                    logger.info(f"⏱️  Total _execute_selenium_command took: {total_elapsed:.2f}s")
                    
                    return result
            except Exception as e:
                if i % 10 == 0:  # Log every 5 seconds
                    logger.debug(f"⏳ Still waiting for response... ({i//2}s elapsed, attempt {i+1})")
            time.sleep(0.5)

        # Check server logs before raising timeout
        log_output = self.sandbox.exec("tail -50 /tmp/selenium.log")
        logger.error(f"Selenium server log (last 50 lines):\n{log_output.stdout}")

        raise TimeoutError(
            f"Selenium command '{command.get('action')}' timed out after {max_wait}s. Check /tmp/selenium.log"
        )

    async def execute(
        self,
        action: str,
        url: Optional[str] = None,
        selector: Optional[str] = None,
        text: Optional[str] = None,
        file_path: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        """
        Execute Selenium web automation action using persistent server
        """
        if not self.sandbox:
            return self.fail_response("E2B sandbox not initialized")

        try:
            # Ensure Selenium server is running
            await self._ensure_selenium_server()

            # Build command for persistent server
            command = {"action": action}
            if url:
                command["url"] = url
            if selector:
                command["selector"] = selector
            if text:
                command["text"] = text
            if file_path:
                command["file_path"] = file_path

            import time as time_module
            execute_start = time_module.time()
            logger.info(f"🌐 Sending Selenium command: {action}")

            # Execute command on persistent server
            command_start = time_module.time()
            output_data = await self._execute_selenium_command(command)
            command_elapsed = time_module.time() - command_start
            logger.debug(f"⏱️  _execute_selenium_command returned after: {command_elapsed:.2f}s")

            if not output_data.get("success"):
                error = output_data.get("error", "Unknown error")
                error_type = output_data.get("error_type", "")
                error_details = output_data.get("error_details", "")
                suggestion = output_data.get("suggestion", "")

                # Build detailed error message
                error_msg = f"❌ {error}"
                if error_type:
                    error_msg += f"\nError Type: {error_type}"
                if error_details:
                    error_msg += f"\nDetails: {error_details[:200]}"
                if suggestion:
                    error_msg += f"\n💡 Suggestion: {suggestion}"

                # Add context info
                if output_data.get("current_url"):
                    error_msg += f"\nCurrent URL: {output_data.get('current_url')}"
                if output_data.get("available_elements"):
                    error_msg += f"\nPage has: {output_data.get('available_elements')}"

                logger.error(f"Selenium error: {error_msg}")
                return self.fail_response(error_msg)

            # Format response based on action
            format_start = time_module.time()
            logger.debug(f"📦 Starting to format response for action: {action}")
            result = self._format_response(action, output_data)
            format_elapsed = time_module.time() - format_start
            logger.debug(f"⏱️  Response formatting took: {format_elapsed:.2f}s")
            
            total_execute = time_module.time() - execute_start
            logger.info(f"⏱️  Total execute() method took: {total_execute:.2f}s")
            
            return result

        except Exception as e:
            logger.error(f"E2B Selenium error: {e}")
            import traceback

            traceback.print_exc()
            return self.fail_response(f"Selenium execution error: {e}")

    def _format_response(self, action: str, data: dict) -> ToolResult:
        """Format Selenium output into readable response"""

        if action == "navigate":
            response = [
                f"✅ Navigated to: {data.get('url')}",
                f"Title: {data.get('title')}",
                f"Found {data.get('element_count', 0)} interactive elements",
                "",
                "Elements:",
            ]

            # Show ALL elements (not just 20)
            for i, elem in enumerate(data.get("elements", []), 1):
                elem_type = elem.get("type", "")
                elem_desc = f"  [{i}] {elem['tag']}"

                if elem_type == "content":
                    elem_desc += " (content-only)"
                elif elem_type and elem_type != "interactive":
                    elem_desc += f" type={elem_type}"

                if elem.get("text"):
                    elem_desc += f" text='{elem['text'][:50]}'"
                if elem.get("id"):
                    elem_desc += f" id='{elem['id']}'"
                if elem.get("class") and any(
                    kw in elem["class"].lower() for kw in ["loading", "error", "alert"]
                ):
                    elem_desc += f" [{elem['class'].split()[0]}]"

                response.append(elem_desc)

            return self.success_response("\n".join(response))

        elif action == "click":
            response = [
                f"✅ {data.get('message', 'Clicked')}",
                f"URL: {data.get('url')}",
                f"Title: {data.get('title')}",
            ]

            # Check if page changed (popup closed, navigation, etc.)
            if data.get("note"):
                response.append(f"ℹ️ {data.get('note')}")

            response.append(f"Found {data.get('element_count', 0)} elements")

            # Only show elements if we got some
            if data.get("element_count", 0) > 0:
                response.append("")
                response.append("Elements After Click:")

                # Show elements after click (like navigate)
                for i, elem in enumerate(data.get("elements", []), 1):
                    elem_type = elem.get("type", "")
                    elem_desc = f"  [{i}] {elem['tag']}"

                    if elem_type == "content":
                        elem_desc += " (content-only)"
                    elif elem_type and elem_type != "interactive":
                        elem_desc += f" type={elem_type}"

                    if elem.get("text"):
                        elem_desc += f" text='{elem['text'][:50]}'"
                    if elem.get("id"):
                        elem_desc += f" id='{elem['id']}'"

                    response.append(elem_desc)
            else:
                response.append("(Click closed modal/popup - this is normal behavior)")

            return self.success_response("\n".join(response))

        elif action == "input_text":
            return self.success_response(f"✅ {data.get('message')}")

        elif action == "get_page_info":
            return self.success_response(
                f"Title: {data.get('title')}\n"
                f"URL: {data.get('url')}\n\n"
                f"Page Text:\n{data.get('page_text')}"
            )

        elif action == "take_screenshot":
            return self.success_response(f"✅ {data.get('message')}")

        else:
            return self.success_response(f"✅ Action completed: {action}")
