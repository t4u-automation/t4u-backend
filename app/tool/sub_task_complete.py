"""Sub-Task Complete Tool - For sub-agents to signal completion without terminating main session"""

from app.tool.base import BaseTool

_SUB_TASK_COMPLETE_DESCRIPTION = """
Signal that a sub-task has been completed successfully.

Use this when you (as a sub-agent) have finished the specific subtask you were assigned.
Provide a brief summary of what was accomplished.

This is different from 'terminate' - it signals completion of a subtask, 
not the entire session.
"""


class SubTaskComplete(BaseTool):
    name: str = "sub_task_complete"
    description: str = _SUB_TASK_COMPLETE_DESCRIPTION
    parameters: dict = {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Brief summary of what was accomplished in this subtask",
            }
        },
        "required": ["summary"],
    }

    async def execute(self, summary: str) -> str:
        """Mark the subtask as complete"""
        return f"Sub-task completed: {summary}"

