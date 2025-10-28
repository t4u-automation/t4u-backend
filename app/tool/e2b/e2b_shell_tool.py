"""E2B Shell Tool - Full parity with SandboxShellTool"""

import asyncio
import time
from typing import Dict, Optional
from uuid import uuid4

from pydantic import Field, PrivateAttr

from app.e2b.tool_base import E2BToolsBase
from app.tool.base import ToolResult
from app.utils.logger import logger

_SHELL_DESCRIPTION = """\
Execute a shell command in the workspace directory.
Commands can be blocking (wait for completion) or non-blocking (run in background).
For quick commands (ls, cat, grep): use blocking=true to get immediate results
For long-running (servers, builds): use blocking=false to run in background tmux session
Uses sessions to maintain state between commands.
This tool is essential for running CLI tools, installing packages, and managing system operations.
"""


class E2BShellTool(E2BToolsBase):
    """
    Tool for executing shell commands in E2B sandbox.
    Matches SandboxShellTool functionality with session management.
    """

    name: str = "e2b_shell"
    description: str = _SHELL_DESCRIPTION
    parameters: dict = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "execute_command",
                    "check_command_output",
                    "terminate_command",
                    "list_commands",
                ],
                "description": "The shell action to perform",
            },
            "command": {
                "type": "string",
                "description": "The shell command to execute. Use this for running CLI tools, installing packages, "
                "or system operations. Commands can be chained using &&, ||, and | operators.",
            },
            "folder": {
                "type": "string",
                "description": "Optional relative path to a subdirectory of /home/user where the command should be "
                "executed. Example: 'data/pdfs'",
            },
            "session_name": {
                "type": "string",
                "description": "Optional name of the tmux session to use. Use named sessions for related commands "
                "that need to maintain state. Defaults to a random session name.",
            },
            "blocking": {
                "type": "boolean",
                "description": "Whether to wait for the command to complete. Set to true for quick commands (ls, cat) "
                "that you need immediate output from. Set to false for long-running commands (servers). "
                "Defaults to true for E2B compatibility.",
                "default": True,
            },
            "timeout": {
                "type": "integer",
                "description": "Optional timeout in seconds for blocking commands. Defaults to 60. Ignored for "
                "non-blocking commands.",
                "default": 60,
            },
            "kill_session": {
                "type": "boolean",
                "description": "Whether to terminate the tmux session after checking. Set to true when you're done "
                "with the command.",
                "default": False,
            },
        },
        "required": ["action"],
        "dependencies": {
            "execute_command": ["command"],
            "check_command_output": ["session_name"],
            "terminate_command": ["session_name"],
            "list_commands": [],
        },
    }

    _sessions: Dict[str, str] = PrivateAttr(default_factory=dict)
    workspace_path: str = Field(default="/home/user", exclude=True)

    async def _check_and_upload_new_files(self, before_list: set):
        """Check for new files created by command and upload as artifacts"""
        try:
            # Get file list after command
            after_files = self.sandbox.exec("ls -1 /home/user 2>/dev/null || true")
            after_list = (
                set(after_files.stdout.strip().split("\n"))
                if after_files.stdout.strip()
                else set()
            )

            # Find new files
            new_files = after_list - before_list

            # Filter out system files and directories
            excluded = {
                ".cache",
                ".bashrc",
                ".bash_logout",
                ".profile",
                "",
                ".fluxbox",
                ".fehbg",
                ".sudo_as_admin_successful",
            }
            new_files = new_files - excluded

            if not new_files:
                return

            # Upload each new file as artifact
            from app.firestore import firestore_client

            session_id = self.session_id if hasattr(self, "session_id") else None
            user_id = self.user_id if hasattr(self, "user_id") else None

            if not session_id or not user_id or not firestore_client.storage_enabled:
                return

            # Get current step number
            step_number = 0
            try:
                import api_server

                if session_id in api_server.active_sessions:
                    agent = api_server.active_sessions[session_id].get("agent")
                    if agent and hasattr(agent, "current_step"):
                        step_number = agent.current_step
            except:
                pass

            for file_name in new_files:
                try:
                    # Read file from E2B
                    file_path = f"/home/user/{file_name}"
                    file_bytes = self.sandbox.filesystem_read(file_path, binary=True)

                    if file_bytes:
                        # Upload artifact
                        public_url = await firestore_client.upload_artifact(
                            user_id=user_id,
                            session_id=session_id,
                            file_path=file_name,
                            file_content=file_bytes,
                            step_number=step_number,
                        )

                        if public_url:
                            logger.info(
                                f"📤 Shell-created artifact uploaded: {file_name}"
                            )
                except Exception as e:
                    logger.warning(
                        f"Failed to upload shell-created file {file_name}: {e}"
                    )

        except Exception as e:
            logger.debug(f"Error checking for new files: {e}")
            # Don't fail shell command if artifact check fails

    async def _execute_command(
        self,
        command: str,
        folder: Optional[str] = None,
        session_name: Optional[str] = None,
        blocking: bool = True,  # Default to blocking for E2B
        timeout: int = 60,
    ) -> ToolResult:
        """Execute a command directly (E2B handles sessions internally)"""
        try:
            if not self.sandbox:
                return self.fail_response("E2B sandbox not initialized")

            # Set up working directory
            cwd = self.workspace_path
            if folder:
                folder = folder.strip("/")
                cwd = f"{self.workspace_path}/{folder}"

            # Generate session name if not provided
            if not session_name:
                session_name = f"session_{str(uuid4())[:8]}"

            # Execute command directly with cd to working directory
            full_command = f"cd {cwd} && {command}"

            # Log to activity monitor
            self.sandbox.exec(
                f"echo '[SHELL] Executing: {command[:80]}...' >> /tmp/agent_activity.log"
            )

            # Focus Activity Monitor window
            # Minimize browser if open
            self.sandbox.exec(
                "DISPLAY=:99 xdotool search --name chromium windowminimize 2>/dev/null || true"
            )
            # Restore Activity Monitor from minimized and bring to front
            self.sandbox.exec(
                "DISPLAY=:99 xdotool search --name 'Activity Monitor' windowmap windowactivate windowraise 2>/dev/null || true"
            )

            # Get file list before command
            before_files = self.sandbox.exec("ls -1 /home/user 2>/dev/null || true")
            before_list = (
                set(before_files.stdout.strip().split("\n"))
                if before_files.stdout.strip()
                else set()
            )

            logger.info(f"Executing command in E2B: {full_command[:100]}...")
            result = self.sandbox.exec(full_command, timeout=timeout)

            # Log result
            if result.exit_code == 0:
                self.sandbox.exec(
                    f"echo '[OK] Command completed' >> /tmp/agent_activity.log"
                )
            else:
                self.sandbox.exec(
                    f"echo '[ERROR] Command failed' >> /tmp/agent_activity.log"
                )

            # Check for new files created by command
            if result.exit_code == 0:
                await self._check_and_upload_new_files(before_list)

            if result.exit_code == 0:
                output = result.stdout if result.stdout else "(no output)"
                return self.success_response(
                    f"Output:\n{output}\n\nSession: {session_name}\nCWD: {cwd}\nCompleted: True"
                )
            else:
                error_msg = f"Command failed with exit code {result.exit_code}\n"
                error_msg += f"Stdout: {result.stdout}\n" if result.stdout else ""
                error_msg += f"Stderr: {result.stderr}" if result.stderr else ""
                return self.fail_response(error_msg)

        except Exception as e:
            logger.error(f"Shell command execution error: {e}")
            return self.fail_response(f"Error executing command: {e}")

    async def _check_command_output(
        self, session_name: str, kill_session: bool = False
    ) -> ToolResult:
        """Check output of a running command"""
        try:
            if not self.sandbox:
                return self.fail_response("E2B sandbox not initialized")

            # Check if session exists
            check_result = self.sandbox.exec(
                f"tmux has-session -t {session_name} 2>/dev/null || echo 'not_exists'"
            )
            if "not_exists" in check_result.stdout:
                return self.fail_response(
                    f"Tmux session '{session_name}' does not exist."
                )

            # Get output
            output_result = self.sandbox.exec(
                f"tmux capture-pane -t {session_name} -p -S - -E -"
            )
            output = output_result.stdout

            # Kill session if requested
            if kill_session:
                self.sandbox.exec(f"tmux kill-session -t {session_name}")
                status = "Session terminated."
            else:
                status = "Session still running."

            return self.success_response(
                f"Output:\n{output}\n\nSession: {session_name}\nStatus: {status}"
            )

        except Exception as e:
            return self.fail_response(f"Error checking command output: {e}")

    async def _terminate_command(self, session_name: str) -> ToolResult:
        """Terminate a running command session"""
        try:
            if not self.sandbox:
                return self.fail_response("E2B sandbox not initialized")

            # Check if session exists
            check_result = self.sandbox.exec(
                f"tmux has-session -t {session_name} 2>/dev/null || echo 'not_exists'"
            )
            if "not_exists" in check_result.stdout:
                return self.fail_response(
                    f"Tmux session '{session_name}' does not exist."
                )

            # Kill the session
            self.sandbox.exec(f"tmux kill-session -t {session_name}")
            return self.success_response(
                f"Tmux session '{session_name}' terminated successfully."
            )

        except Exception as e:
            return self.fail_response(f"Error terminating command: {e}")

    async def _list_commands(self) -> ToolResult:
        """List all active tmux sessions"""
        try:
            if not self.sandbox:
                return self.fail_response("E2B sandbox not initialized")

            result = self.sandbox.exec(
                "tmux list-sessions 2>/dev/null || echo 'No sessions'"
            )
            output = result.stdout

            if "No sessions" in output or not output.strip():
                return self.success_response(
                    "No active tmux sessions found.\nSessions: []"
                )

            # Parse sessions
            sessions = []
            for line in output.split("\n"):
                if line.strip():
                    parts = line.split(":")
                    if parts:
                        sessions.append(parts[0].strip())

            return self.success_response(
                f"Found {len(sessions)} active sessions.\nSessions: {sessions}"
            )

        except Exception as e:
            return self.fail_response(f"Error listing commands: {e}")

    async def execute(
        self,
        action: str,
        command: Optional[str] = None,
        folder: Optional[str] = None,
        session_name: Optional[str] = None,
        blocking: bool = True,  # Changed to True to match _execute_command default
        timeout: int = 60,
        kill_session: bool = False,
        **kwargs,
    ) -> ToolResult:
        """Execute a shell action"""
        async with asyncio.Lock():
            try:
                if action == "execute_command":
                    if not command:
                        return self.fail_response("command is required")
                    return await self._execute_command(
                        command, folder, session_name, blocking, timeout
                    )
                elif action == "check_command_output":
                    if not session_name:
                        return self.fail_response("session_name is required")
                    return await self._check_command_output(session_name, kill_session)
                elif action == "terminate_command":
                    if not session_name:
                        return self.fail_response("session_name is required")
                    return await self._terminate_command(session_name)
                elif action == "list_commands":
                    return await self._list_commands()
                else:
                    return self.fail_response(f"Unknown action: {action}")
            except Exception as e:
                logger.error(f"Error executing shell action: {e}")
                return self.fail_response(f"Error executing shell action: {e}")

    async def cleanup(self):
        """Clean up all sessions"""
        try:
            if self.sandbox:
                self.sandbox.exec("tmux kill-server 2>/dev/null || true")
        except Exception as e:
            logger.error(f"Error in shell cleanup: {e}")
