"""Base class for E2B sandbox tools"""

from typing import Optional

from pydantic import Field, PrivateAttr

from app.e2b.sandbox import E2BSandbox
from app.tool.base import BaseTool, ToolResult
from app.utils.logger import logger


class E2BToolsBase(BaseTool):
    """
    Base class for tools that operate within E2B sandboxes.
    Provides common functionality for E2B-based tool execution.
    """

    _sandbox: Optional[E2BSandbox] = PrivateAttr(default=None)
    _urls_printed: bool = PrivateAttr(default=False)
    _session_id: Optional[str] = PrivateAttr(default=None)
    _user_id: Optional[str] = PrivateAttr(default=None)

    def __init__(
        self,
        sandbox: Optional[E2BSandbox] = None,
        session_id: str = None,
        user_id: str = None,
        **data,
    ):
        """Initialize with optional sandbox and session context."""
        super().__init__(**data)
        if sandbox is not None:
            self._sandbox = sandbox
        self._session_id = session_id
        self._user_id = user_id

    @property
    def sandbox(self) -> Optional[E2BSandbox]:
        """Get the sandbox instance."""
        return self._sandbox

    @property
    def session_id(self) -> Optional[str]:
        """Get the session ID."""
        return self._session_id

    @property
    def user_id(self) -> Optional[str]:
        """Get the user ID."""
        return self._user_id

    def set_sandbox(self, sandbox: E2BSandbox):
        """Set the sandbox instance."""
        self._sandbox = sandbox
        logger.debug(f"Sandbox {sandbox.id} assigned to {self.name}")

    def set_session_context(self, session_id: str, user_id: str, current_step: int = 0):
        """Set the session context for artifact tracking.
        
        Args:
            session_id: Session ID
            user_id: User ID
            current_step: Current step number (for sub-agents to continue numbering)
        """
        self._session_id = session_id
        self._user_id = user_id
        self._current_step = current_step
        # Suppress verbose debug log (still logged to file)

    def success_response(self, msg: str) -> ToolResult:
        """Create a success response."""
        return ToolResult(output=msg)

    def fail_response(self, msg: str) -> ToolResult:
        """Create a failure response."""
        return ToolResult(error=msg)
