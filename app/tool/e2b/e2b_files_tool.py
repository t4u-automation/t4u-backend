"""E2B Files Tool - Full parity with SandboxFilesTool"""

import asyncio
from typing import Optional

from pydantic import Field

from app.e2b.tool_base import E2BToolsBase
from app.tool.base import ToolResult
from app.utils.files_utils import clean_path, should_exclude_file
from app.utils.logger import logger

_FILES_DESCRIPTION = """\
A sandbox-based file system tool that allows file operations in a secure sandboxed environment.
* This tool provides commands for creating, reading, updating, and deleting files in the workspace
* All operations are performed relative to the /home/user directory for security
* Use this when you need to manage files, edit code, or manipulate file contents in a sandbox
* Each action requires specific parameters as defined in the tool's dependencies
Key capabilities include:
* File creation: Create new files with specified content and permissions
* File modification: Replace specific strings or completely rewrite files
* File deletion: Remove files from the workspace
* File reading: Read file contents with optional line range specification
"""


class E2BFilesTool(E2BToolsBase):
    """Tool for file operations in E2B sandbox - matches SandboxFilesTool API"""

    name: str = "e2b_files"
    description: str = _FILES_DESCRIPTION
    parameters: dict = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "create_file",
                    "str_replace",
                    "full_file_rewrite",
                    "delete_file",
                ],
                "description": "The file operation to perform",
            },
            "file_path": {
                "type": "string",
                "description": "Path to the file, relative to /home/user (e.g., 'src/main.py')",
            },
            "file_contents": {
                "type": "string",
                "description": "Content to write to the file",
            },
            "old_str": {
                "type": "string",
                "description": "Text to be replaced (must appear exactly once)",
            },
            "new_str": {
                "type": "string",
                "description": "Replacement text",
            },
            "permissions": {
                "type": "string",
                "description": "File permissions in octal format (e.g., '644')",
                "default": "644",
            },
        },
        "required": ["action"],
        "dependencies": {
            "create_file": ["file_path", "file_contents"],
            "str_replace": ["file_path", "old_str", "new_str"],
            "full_file_rewrite": ["file_path", "file_contents"],
            "delete_file": ["file_path"],
        },
    }

    SNIPPET_LINES: int = Field(default=4, exclude=True)
    workspace_path: str = Field(default="/home/user", exclude=True)

    def clean_path(self, path: str) -> str:
        """Clean and normalize a path"""
        return clean_path(path, self.workspace_path)

    async def _upload_artifact(self, file_path: str, file_contents: str):
        """Upload file to Firebase Storage with user_id path"""
        try:
            from app.firestore import firestore_client

            # Use session context from tool instance (set during initialization)
            session_id = self.session_id if hasattr(self, "session_id") else None
            user_id = self.user_id if hasattr(self, "user_id") else None

            # Get current step number if possible
            step_number = 0
            try:
                import api_server

                if session_id and session_id in api_server.active_sessions:
                    agent = api_server.active_sessions[session_id].get("agent")
                    if agent and hasattr(agent, "current_step"):
                        step_number = agent.current_step
            except:
                pass

            if not session_id or not user_id:
                logger.warning(
                    f"⚠️ No session context for artifact upload (session_id={session_id}, user_id={user_id})"
                )
                return

            if not firestore_client.storage_enabled:
                logger.info("Firebase Storage not enabled, skipping artifact upload")
                return

            # Read file content from E2B
            full_path = f"{self.workspace_path}/{file_path}"

            try:
                file_bytes = self.sandbox.filesystem_read(full_path, binary=True)
            except Exception as e:
                logger.warning(f"Could not read file from E2B: {e}")
                # Fallback: use the file_contents passed as parameter
                if isinstance(file_contents, str):
                    file_bytes = file_contents.encode("utf-8")
                else:
                    file_bytes = file_contents

            if not file_bytes:
                logger.warning(f"No file content for {file_path}")
                return

            # Upload with user_id in path
            logger.info(
                f"Uploading artifact: {file_path} for user {user_id}, session {session_id}"
            )

            public_url = await firestore_client.upload_artifact(
                user_id=user_id,
                session_id=session_id,
                file_path=file_path,
                file_content=file_bytes,
                step_number=step_number,
            )

            if public_url:
                logger.info(
                    f"✅ Artifact uploaded successfully: {file_path} → {public_url}"
                )
            else:
                logger.warning(f"Artifact upload returned no URL for {file_path}")

        except Exception as e:
            logger.error(f"❌ Artifact upload exception for {file_path}: {e}")
            import traceback

            traceback.print_exc()
            # Don't fail the file operation if upload fails

    def _should_exclude_file(self, rel_path: str) -> bool:
        """Check if a file should be excluded"""
        return should_exclude_file(rel_path)

    def _file_exists(self, path: str) -> bool:
        """Check if a file exists"""
        try:
            # Use ls to check file existence
            result = self.sandbox.exec(
                f"ls {path} 2>/dev/null && echo 'FILE_EXISTS' || echo 'FILE_NOT_EXISTS'"
            )

            # Check for exact match (not substring)
            return (
                "FILE_EXISTS" in result.stdout
                and "FILE_NOT_EXISTS" not in result.stdout
            )
        except Exception as e:
            logger.error(f"Error checking file existence: {e}")
            return False

    async def _create_file(
        self, file_path: str, file_contents: str, permissions: str = "644"
    ) -> ToolResult:
        """Create a new file"""
        try:
            if not self.sandbox:
                return self.fail_response("E2B sandbox not initialized")

            file_path = self.clean_path(file_path)
            full_path = f"{self.workspace_path}/{file_path}"

            if self._file_exists(full_path):
                return self.fail_response(
                    f"File '{file_path}' already exists. Use full_file_rewrite to modify existing files."
                )

            # Log to activity monitor
            self.sandbox.exec(
                f"echo '[FILE] Creating file: {file_path}' >> /tmp/agent_activity.log"
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

            # Create parent directories
            parent_dir = "/".join(full_path.split("/")[:-1])
            if parent_dir:
                self.sandbox.exec(f"mkdir -p {parent_dir}")

            # Write file
            self.sandbox.filesystem_write(full_path, file_contents)
            self.sandbox.exec(f"chmod {permissions} {full_path}")

            # Log success
            self.sandbox.exec(
                f"echo '[OK] File created: {file_path} ({len(file_contents)} bytes)' >> /tmp/agent_activity.log"
            )

            # Upload artifact to Firebase Storage
            await self._upload_artifact(file_path, file_contents)

            return self.success_response(f"File '{file_path}' created successfully.")

        except Exception as e:
            return self.fail_response(f"Error creating file: {e}")

    async def _str_replace(
        self, file_path: str, old_str: str, new_str: str
    ) -> ToolResult:
        """Replace specific text in a file"""
        try:
            if not self.sandbox:
                return self.fail_response("E2B sandbox not initialized")

            file_path = self.clean_path(file_path)
            full_path = f"{self.workspace_path}/{file_path}"

            if not self._file_exists(full_path):
                return self.fail_response(f"File '{file_path}' does not exist")

            content = self.sandbox.filesystem_read(full_path)
            old_str = old_str.expandtabs()
            new_str = new_str.expandtabs()

            occurrences = content.count(old_str)
            if occurrences == 0:
                return self.fail_response(
                    f"String '{old_str[:50]}...' not found in file"
                )
            if occurrences > 1:
                lines = [
                    i + 1
                    for i, line in enumerate(content.split("\n"))
                    if old_str in line
                ]
                return self.fail_response(
                    f"Multiple occurrences found in lines {lines}. Please ensure string is unique"
                )

            # Perform replacement
            new_content = content.replace(old_str, new_str)
            self.sandbox.filesystem_write(full_path, new_content)

            return self.success_response(f"Replacement successful in '{file_path}'.")

        except Exception as e:
            return self.fail_response(f"Error replacing string: {e}")

    async def _full_file_rewrite(
        self, file_path: str, file_contents: str, permissions: str = "644"
    ) -> ToolResult:
        """Completely rewrite an existing file"""
        try:
            if not self.sandbox:
                return self.fail_response("E2B sandbox not initialized")

            file_path = self.clean_path(file_path)
            full_path = f"{self.workspace_path}/{file_path}"

            if not self._file_exists(full_path):
                return self.fail_response(
                    f"File '{file_path}' does not exist. Use create_file to create a new file."
                )

            # Log to activity monitor
            self.sandbox.exec(
                f"echo '[FILE] Rewriting file: {file_path}' >> /tmp/agent_activity.log"
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

            self.sandbox.filesystem_write(full_path, file_contents)
            self.sandbox.exec(f"chmod {permissions} {full_path}")

            # Log success
            self.sandbox.exec(
                f"echo '[OK] File rewritten: {file_path} ({len(file_contents)} bytes)' >> /tmp/agent_activity.log"
            )

            # Upload artifact to Firebase Storage (new version)
            await self._upload_artifact(file_path, file_contents)

            return self.success_response(
                f"File '{file_path}' completely rewritten successfully."
            )

        except Exception as e:
            return self.fail_response(f"Error rewriting file: {e}")

    async def _delete_file(self, file_path: str) -> ToolResult:
        """Delete a file"""
        try:
            if not self.sandbox:
                return self.fail_response("E2B sandbox not initialized")

            file_path = self.clean_path(file_path)
            full_path = f"{self.workspace_path}/{file_path}"

            if not self._file_exists(full_path):
                return self.fail_response(f"File '{file_path}' does not exist")

            result = self.sandbox.exec(f"rm {full_path}")
            if result.exit_code == 0:
                return self.success_response(
                    f"File '{file_path}' deleted successfully."
                )
            else:
                return self.fail_response(f"Failed to delete file: {result.stderr}")

        except Exception as e:
            return self.fail_response(f"Error deleting file: {e}")

    async def execute(
        self,
        action: str,
        file_path: Optional[str] = None,
        file_contents: Optional[str] = None,
        old_str: Optional[str] = None,
        new_str: Optional[str] = None,
        permissions: Optional[str] = "644",
        **kwargs,
    ) -> ToolResult:
        """Execute a file operation"""
        async with asyncio.Lock():
            try:
                if action == "create_file":
                    if not file_path or file_contents is None:
                        return self.fail_response(
                            "file_path and file_contents are required for create_file"
                        )
                    return await self._create_file(
                        file_path, file_contents, permissions
                    )

                elif action == "str_replace":
                    if not file_path or not old_str or new_str is None:
                        return self.fail_response(
                            "file_path, old_str, and new_str are required for str_replace"
                        )
                    return await self._str_replace(file_path, old_str, new_str)

                elif action == "full_file_rewrite":
                    if not file_path or file_contents is None:
                        return self.fail_response(
                            "file_path and file_contents are required for full_file_rewrite"
                        )
                    return await self._full_file_rewrite(
                        file_path, file_contents, permissions
                    )

                elif action == "delete_file":
                    if not file_path:
                        return self.fail_response(
                            "file_path is required for delete_file"
                        )
                    return await self._delete_file(file_path)

                else:
                    return self.fail_response(f"Unknown action: {action}")

            except Exception as e:
                logger.error(f"Error executing file action: {e}")
                return self.fail_response(f"Error executing file action: {e}")
