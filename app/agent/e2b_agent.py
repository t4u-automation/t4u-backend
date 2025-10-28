"""E2B-based TestOpsAI Agent with full internet access"""

from typing import Optional

from pydantic import Field, model_validator

from app.agent.toolcall import ToolCallAgent
from app.config import config
from app.e2b.sandbox import E2BSandbox, create_sandbox, delete_sandbox
from app.logger import logger
from app.prompt.testopsai import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.tool import Terminate, ToolCollection
from app.tool.ai_proven_steps import AIProvenSteps
from app.tool.e2b.e2b_browser_tool import E2BBrowserTool
from app.tool.e2b.e2b_crawl4ai_tool import E2BCrawl4AITool
from app.tool.e2b.e2b_files_tool import E2BFilesTool
from app.tool.e2b.e2b_shell_tool import E2BShellTool
from app.tool.e2b.e2b_sub_agent_tool import E2BSubAgentTool
from app.tool.e2b.e2b_vision_tool import E2BVisionTool
from app.tool.e2b.e2b_web_search_tool import E2BWebSearchTool
# from app.tool.e2b.e2b_selenium_tool import E2BSeleniumTool  # Not using Selenium
from app.tool.planning import PlanningTool


class E2BTestOpsAI(ToolCallAgent):
    """
    TestOpsAI agent using E2B sandbox with full internet access.
    Web automation agent with browser and vision capabilities.
    """

    name: str = "E2BTestOpsAI"
    description: str = (
        "A versatile agent using E2B sandbox with full unrestricted internet access"
    )

    system_prompt: str = SYSTEM_PROMPT.format(directory=config.workspace_root)
    next_step_prompt: str = NEXT_STEP_PROMPT

    max_observe: int = 10000
    max_steps: int = 20

    # Tools available to the agent
    # Note: E2B tools (web_search, crawl4ai, shell, files, browser, vision) are added in initialize_e2b_sandbox
    available_tools: ToolCollection = Field(
        default_factory=lambda: ToolCollection(
            PlanningTool(),
            AIProvenSteps(),
            Terminate(),
        )
    )
    
    # Note: AIProvenSteps should be called BEFORE Terminate to save execution history

    special_tool_names: list[str] = Field(default_factory=lambda: [Terminate().name])
    sandbox: Optional[E2BSandbox] = None
    _initialized: bool = False
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    test_case_id: Optional[str] = None

    @classmethod
    async def create(
        cls,
        session_id: str = None,
        user_id: str = None,
        tenant_id: str = None,
        test_case_id: str = None,
        **kwargs,
    ) -> "E2BTestOpsAI":
        """Factory method to create and properly initialize E2BTestOpsAI instance."""
        from datetime import datetime

        instance = cls(**kwargs)
        instance.session_id = session_id or datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        instance.user_id = user_id
        instance.tenant_id = tenant_id
        instance.test_case_id = test_case_id

        await instance.initialize_e2b_sandbox()
        instance._initialized = True
        return instance

    async def initialize_e2b_sandbox(self) -> None:
        """Initialize E2B sandbox and tools."""
        try:
            if not config.e2b or not config.e2b.e2b_api_key:
                raise ValueError(
                    "E2B not configured. Please set e2b_api_key in config.toml. "
                    "Get your API key from https://e2b.dev/docs"
                )

            logger.info("Initializing E2B sandbox...")

            # Send sandbox initializing to Firestore
            try:
                from datetime import datetime

                from app.firestore import firestore_client
                from app.webhook import StepExecutionSchema

                step_data = StepExecutionSchema(
                    step_number=0,
                    timestamp=datetime.utcnow().isoformat() + "Z",
                    agent_name=self.name,
                    session_id=getattr(self, "session_id", None),
                    user_id=getattr(self, "user_id", None),
                    tenant_id=getattr(self, "tenant_id", None),
                    test_case_id=getattr(self, "test_case_id", None),
                    event_type="sandbox_initializing",
                    status="initializing",
                )

                if firestore_client.enabled:
                    await firestore_client.save_step(step_data, [])
            except:
                pass

            # Create E2B sandbox
            self.sandbox = await create_sandbox()

            logger.info(f"E2B Sandbox ID: {self.sandbox.id}")
            logger.info("E2B sandbox has FULL INTERNET ACCESS - no tier restrictions!")

            # Send sandbox ready to Firestore
            try:
                from datetime import datetime

                from app.firestore import firestore_client
                from app.webhook import StepExecutionSchema

                step_data = StepExecutionSchema(
                    step_number=0,
                    timestamp=datetime.utcnow().isoformat() + "Z",
                    agent_name=self.name,
                    session_id=getattr(self, "session_id", None),
                    user_id=getattr(self, "user_id", None),
                    tenant_id=getattr(self, "tenant_id", None),
                    test_case_id=getattr(self, "test_case_id", None),
                    event_type="sandbox_ready",
                    status="ready",
                    sandbox_id=self.sandbox.id,
                )

                if firestore_client.enabled:
                    await firestore_client.save_step(step_data, [])
            except:
                pass

            # Connect to stream servers if running
            try:
                import importlib.util
                import sys

                # Screenshot stream server
                stream_path = config.workspace_root.parent / "stream_server.py"
                spec = importlib.util.spec_from_file_location(
                    "stream_server", stream_path
                )
                if spec and spec.loader:
                    stream_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(stream_module)
                    stream_module.set_sandbox(self.sandbox)

                # Desktop stream server
                desktop_path = config.workspace_root.parent / "e2b_desktop_stream.py"
                spec2 = importlib.util.spec_from_file_location(
                    "e2b_desktop_stream", desktop_path
                )
                if spec2 and spec2.loader:
                    desktop_module = importlib.util.module_from_spec(spec2)
                    spec2.loader.exec_module(desktop_module)
                    desktop_module.set_sandbox(self.sandbox)

                # VNC proxy server
                vnc_path = config.workspace_root.parent / "vnc_proxy.py"
                spec3 = importlib.util.spec_from_file_location("vnc_proxy", vnc_path)
                if spec3 and spec3.loader:
                    vnc_module = importlib.util.module_from_spec(spec3)
                    spec3.loader.exec_module(vnc_module)
                    vnc_module.set_sandbox(self.sandbox)
            except Exception as e:
                pass  # Stream servers optional

            # Create E2B tools (3 tools: browser, vision, sub-agent)
            e2b_tools = [
                E2BBrowserTool(sandbox=self.sandbox),     # Playwright - web automation
                E2BVisionTool(sandbox=self.sandbox),      # Screenshots + OCR
                E2BSubAgentTool(sandbox=self.sandbox),    # Delegate subtasks
                # Disabled tools - restricting to browser + vision + sub-agent:
                # E2BShellTool(sandbox=self.sandbox),
                # E2BFilesTool(sandbox=self.sandbox),
                # E2BCrawl4AITool(sandbox=self.sandbox),
                # E2BWebSearchTool(sandbox=self.sandbox),
                # E2BSeleniumTool(sandbox=self.sandbox),
            ]

            # Set session context on all tools for artifact tracking
            if self.session_id and self.user_id:
                for tool in e2b_tools:
                    if hasattr(tool, "set_session_context"):
                        # Pass current_step so sub-agent can continue numbering
                        tool.set_session_context(self.session_id, self.user_id, self.current_step)
                logger.info(
                    f"Session context set on tools: session_id={self.session_id}, user_id={self.user_id}"
                )

            self.available_tools.add_tools(*e2b_tools)
            logger.info("E2B tools initialized successfully")
            
            # Link ai_proven_steps tool to agent (for accessing execution_history)
            ai_proven_steps_tool = self.available_tools.get_tool("ai_proven_steps")
            if ai_proven_steps_tool and hasattr(ai_proven_steps_tool, 'set_agent'):
                ai_proven_steps_tool.set_agent(self)
                logger.debug("✅ ai_proven_steps tool linked to agent")
            
            # Link sub-agent tool to parent agent and tools
            for tool in e2b_tools:
                if hasattr(tool, 'name') and tool.name == 'e2b_sub_agent':
                    tool.set_parent_tools(self.available_tools)
                    tool.set_parent_agent(self)  # Pass agent reference for current_step
                    logger.debug("✅ Sub-agent tool linked to parent agent and tools")
            
            # Auto-start browser and make it visible/focused (for TestOpsAI browser automation)
            logger.info("Starting browser automatically...")
            try:
                browser_tool = None
                for tool in e2b_tools:
                    if hasattr(tool, 'name') and tool.name == 'e2b_browser':
                        browser_tool = tool
                        break
                
                if browser_tool:
                    # Start browser server (it will be ready for first action)
                    await browser_tool._ensure_browser_server()
                    logger.info("✅ Browser started and ready - visible in VNC!")
                else:
                    logger.warning("Browser tool not found - skipping auto-start")
            except Exception as e:
                logger.warning(f"Browser auto-start failed (will start on first use): {e}")

        except Exception as e:
            logger.error(f"Error initializing E2B sandbox: {e}")
            raise

    async def cleanup(self):
        """Clean up E2B agent resources."""
        if self._initialized and self.sandbox:
            logger.info("Cleaning up E2B sandbox...")
            delete_sandbox(self.sandbox)
            self._initialized = False
            logger.info("E2B cleanup complete")
