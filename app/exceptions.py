class ToolError(Exception):
    """Raised when a tool encounters an error."""

    def __init__(self, message):
        self.message = message


class TestOpsAIError(Exception):
    """Base exception for all TestOpsAI errors"""


class TokenLimitExceeded(TestOpsAIError):
    """Exception raised when the token limit is exceeded"""
