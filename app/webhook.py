"""Webhook client for sending step execution data to external API"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel

from app.config import config


class StepExecutionSchema(BaseModel):
    """Schema for step execution data"""

    step_number: int
    timestamp: str
    agent_name: str
    user_id: Optional[str] = None  # Firebase UID - link to users collection
    session_id: Optional[str] = None  # Link to agent_sessions
    tenant_id: Optional[str] = None  # Tenant/Organization ID
    test_case_id: Optional[str] = None  # Test Case ID
    event_type: str = (
        "step"  # "step", "sandbox_ready", "completed", "human_input_required"
    )
    thinking: Optional[str] = None
    tool_calls: List[Dict[str, Any]] = []
    tool_results: List[Dict[str, Any]] = []
    screenshots: List[str] = []
    screenshot_urls: List[str] = []  # Firebase Storage URLs
    status: str  # "success", "error", "thinking", "initializing", "pending_upload", "waiting_for_human"
    error: Optional[str] = None
    sandbox_id: Optional[str] = None
    human_question: Optional[str] = None  # Question asked to human
    human_response: Optional[str] = None  # Response from human

    class Config:
        json_schema_extra = {
            "example": {
                "step_number": 1,
                "timestamp": "2025-10-01T19:30:00Z",
                "agent_name": "E2BTestOpsAI",
                "thinking": "I need to navigate to the website",
                "tool_calls": [
                    {
                        "tool_name": "e2b_browser",
                        "action": "navigate_to",
                        "arguments": {"url": "https://example.com"},
                    }
                ],
                "tool_results": [
                    {
                        "tool_name": "e2b_browser",
                        "success": True,
                        "output": "Successfully navigated...",
                    }
                ],
                "screenshots": ["screenshot_navigate.png"],
                "status": "success",
            }
        }


class WebhookClient:
    """Client for sending webhook events"""

    def __init__(self):
        self.enabled = False
        self.endpoint = None
        self.api_key = None

        # Check if webhook is configured
        if hasattr(config, "webhook") and config.webhook:
            self.enabled = getattr(config.webhook, "enabled", False)
            self.endpoint = getattr(config.webhook, "endpoint", None)
            self.api_key = getattr(config.webhook, "api_key", None)

            # Must have endpoint and api_key if enabled
            if self.enabled and not (self.endpoint and self.api_key):
                print("⚠️  Webhook enabled but missing endpoint or api_key")
                self.enabled = False

    async def send_sandbox_initializing(self, agent_name: str) -> bool:
        """Send sandbox initializing event"""
        if not self.enabled:
            return False

        try:
            from app.firestore import firestore_client

            step_data = StepExecutionSchema(
                step_number=0,
                timestamp=datetime.utcnow().isoformat() + "Z",
                agent_name=agent_name,
                session_id=None,  # No session yet
                event_type="sandbox_initializing",
                status="initializing",
            )

            # Send to webhook
            if self.enabled:
                await self.send_step_data(step_data)

            # Firestore save is handled elsewhere to avoid duplicates

            return True
        except Exception as e:
            print(f"⚠️  Sandbox initializing webhook error: {e}")
            return False

    async def send_sandbox_ready(self, agent_name: str, sandbox_id: str) -> bool:
        """Send sandbox ready event"""
        if not self.enabled:
            return False

        try:
            from app.firestore import firestore_client

            step_data = StepExecutionSchema(
                step_number=0,
                timestamp=datetime.utcnow().isoformat() + "Z",
                agent_name=agent_name,
                session_id=None,  # Session will be set later
                event_type="sandbox_ready",
                status="ready",
                sandbox_id=sandbox_id,
            )

            # Send to webhook
            if self.enabled:
                await self.send_step_data(step_data)

            # Firestore save is handled elsewhere to avoid duplicates

            return True
        except Exception as e:
            print(f"⚠️  Sandbox ready webhook error: {e}")
            return False

    async def send_step_data(self, step_data: StepExecutionSchema) -> bool:
        """Send step execution data to webhook endpoint"""
        if not self.enabled:
            return False

        try:
            headers = {"Content-Type": "application/json", "x-api-key": self.api_key}

            payload = step_data.model_dump()

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.endpoint, json=payload, headers=headers
                )

                if response.status_code in [200, 201]:
                    print(f"📤 Webhook sent: Step {step_data.step_number}")
                    return True
                else:
                    print(f"⚠️  Webhook failed: HTTP {response.status_code}")
                    return False

        except Exception as e:
            print(f"⚠️  Webhook error: {type(e).__name__}: {str(e)}")
            import traceback

            traceback.print_exc()
            return False


# Global webhook client
webhook_client = WebhookClient()
