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
            
            # Write session metadata to sandbox for websockify JWT validation
            # CRITICAL: Must write BEFORE executing shared test cases so VNC can authenticate
            if hasattr(self, 'session_id') and self.session_id:
                try:
                    import json as json_module
                    from api_server import get_firebase_project_id
                    
                    session_metadata = {
                        "user_id": getattr(self, 'user_id', None),
                        "tenant_id": getattr(self, 'tenant_id', None),
                        "firebase_project_id": get_firebase_project_id()
                    }
                    metadata_json = json_module.dumps(session_metadata)
                    
                    # Write and verify metadata with retry
                    metadata_written = False
                    for attempt in range(3):
                        try:
                            self.sandbox.filesystem_write(
                                "/home/user/.vnc_sessions.json",
                                metadata_json
                            )
                            
                            # Verify it was written
                            try:
                                check = self.sandbox.filesystem_read("/home/user/.vnc_sessions.json")
                                if check and len(check) > 0:
                                    metadata_written = True
                                    logger.info(f"✅ Session metadata written to sandbox (attempt {attempt + 1})")
                                    break
                            except Exception as verify_error:
                                logger.warning(f"⚠️  Metadata verification failed (attempt {attempt + 1}): {verify_error}")
                                
                        except Exception as e:
                            logger.warning(f"⚠️  Failed to write session metadata (attempt {attempt + 1}): {e}")
                        
                        if attempt < 2:
                            import asyncio
                            await asyncio.sleep(0.5)  # Wait before retry
                    
                    if not metadata_written:
                        logger.error("❌ Failed to write session metadata - VNC authentication may fail")
                    
                    # Update VNC URL in Firestore ONLY if this is an AI Exploration session
                    # (not a RUN/replay which uses different Firestore collection)
                    is_replay_session = self.session_id and "_replay" in self.session_id
                    if not is_replay_session:
                        vnc_url = None
                        if hasattr(self.sandbox, "sandbox"):
                            try:
                                host = self.sandbox.sandbox.get_host(6080)
                                vnc_url = f"wss://{host}/websockify"
                                
                                # Update session with VNC URL (only for exploration sessions)
                                await firestore_client.update_session_vnc_url(self.session_id, vnc_url)
                                logger.info(f"✅ VNC URL updated in Firestore agent_sessions: {vnc_url}")
                            except Exception as e:
                                logger.debug(f"VNC URL update skipped or failed: {e}")
                except Exception as e:
                    logger.debug(f"Failed to update VNC/session metadata: {e}")
            
            # Execute BEFORE shared test cases ONLY for AI Exploration sessions
            # NOT for RUN/replay sessions (those handle before/after in execute_test_case_proven_steps)
            is_replay_session = hasattr(self, 'session_id') and self.session_id and "_replay" in self.session_id
            is_exploration_session = hasattr(self, 'test_case_id') and self.test_case_id and hasattr(self, 'tenant_id') and self.tenant_id
            
            if is_exploration_session and not is_replay_session:
                logger.info("🤖 This is an AI Exploration session - executing before shared test cases")
                await self._execute_before_shared_test_cases()
            elif is_replay_session:
                logger.info("🔄 This is a RUN/replay session - before/after test cases handled by execute_test_case_proven_steps")

        except Exception as e:
            logger.error(f"Error initializing E2B sandbox: {e}")
            raise

    async def _execute_before_shared_test_cases(self):
        """
        Execute BEFORE shared test cases during AI Exploration session initialization.
        
        This runs before AI Exploration starts, setting up the browser state
        (e.g., logging in, navigating to a specific page).
        """
        try:
            from app.utils.shared_test_cases import (
                get_test_case_data,
                resolve_shared_test_cases,
                CircularDependencyError,
                SharedTestCaseNotFoundError
            )
            
            logger.info(f"Checking for BEFORE shared test cases for test_case_id: {self.test_case_id}")
            
            # Get test case data
            test_case_data = await get_test_case_data(self.test_case_id, self.tenant_id)
            if not test_case_data:
                logger.warning(f"Test case {self.test_case_id} not found - skipping before test cases")
                return
            
            # Check for shared test cases
            shared_test_cases = test_case_data.get("shared_test_cases", {})
            before_tc_ids = shared_test_cases.get("before", [])
            
            if not before_tc_ids:
                logger.info("No BEFORE shared test cases configured")
                return
            
            logger.info(f"Found {len(before_tc_ids)} BEFORE shared test cases: {before_tc_ids}")
            
            # Resolve recursively to get all before test cases
            try:
                resolved = await resolve_shared_test_cases(self.test_case_id, self.tenant_id)
                all_before_tc_ids = resolved.get("before", [])
                
                if not all_before_tc_ids:
                    logger.info("No BEFORE test cases after resolution")
                    return
                
                logger.info(f"Resolved to {len(all_before_tc_ids)} total BEFORE test cases: {all_before_tc_ids}")
                
            except CircularDependencyError as e:
                logger.error(f"Circular dependency in shared test cases: {e}")
                return
            except SharedTestCaseNotFoundError as e:
                logger.error(f"Shared test case not found: {e}")
                return
            
            # Execute each before test case
            logger.info("\n" + "="*70)
            logger.info(f"🔷 EXECUTING BEFORE TEST CASES ({len(all_before_tc_ids)})")
            logger.info("="*70)
            
            for idx, before_tc_id in enumerate(all_before_tc_ids):
                logger.info(f"\n▶ [{idx + 1}/{len(all_before_tc_ids)}] Executing BEFORE: {before_tc_id}")
                
                # Get before test case data
                before_tc_data = await get_test_case_data(before_tc_id, self.tenant_id)
                if not before_tc_data:
                    logger.error(f"Before test case not found: {before_tc_id}")
                    continue
                
                # Send before test case START event to Firestore
                try:
                    from datetime import datetime
                    from app.firestore import firestore_client
                    from app.webhook import StepExecutionSchema
                    
                    start_event = StepExecutionSchema(
                        step_number=0,
                        timestamp=datetime.utcnow().isoformat() + "Z",
                        agent_name=self.name,
                        session_id=getattr(self, "session_id", None),
                        user_id=getattr(self, "user_id", None),
                        tenant_id=getattr(self, "tenant_id", None),
                        test_case_id=getattr(self, "test_case_id", None),
                        event_type="before_test_case_start",
                        status="running",
                        thinking=f"Executing before test case {idx + 1}/{len(all_before_tc_ids)}: {before_tc_data.get('summary', before_tc_id)}"
                    )
                    
                    if firestore_client.enabled:
                        await firestore_client.save_step(start_event, [])
                except Exception as e:
                    logger.debug(f"Failed to send before_test_case_start event: {e}")
                
                proven_steps = before_tc_data.get("proven_steps", [])
                if not proven_steps:
                    logger.warning(f"No proven steps in before test case: {before_tc_id}")
                    continue
                
                logger.info(f"  Executing {len(proven_steps)} proven steps...")
                
                # Execute each proven step
                passed = 0
                failed = 0
                
                for step_idx, step in enumerate(proven_steps):
                    # Handle both formats: {tool_name, arguments} OR {action: {tool_name, arguments}}
                    if "action" in step and isinstance(step["action"], dict):
                        tool_name = step["action"].get("tool_name")
                        arguments = step["action"].get("arguments", {})
                    else:
                        tool_name = step.get("tool_name")
                        arguments = step.get("arguments", {})
                    
                    logger.info(f"    Step {step_idx + 1}/{len(proven_steps)}: {tool_name} {arguments.get('action', '')}")
                    
                    # Get tool
                    tool = self.available_tools.get_tool(tool_name)
                    if not tool:
                        logger.error(f"    ❌ Tool {tool_name} not found")
                        failed += 1
                        break
                    
                    # Execute step
                    try:
                        result = await tool.execute(**arguments)
                        has_error = (hasattr(result, 'error') and result.error) or str(result).startswith("Error:")
                        
                        if has_error:
                            logger.error(f"    ❌ Failed: {str(result)[:100]}")
                            failed += 1
                            # Stop on error in before test cases
                            break
                        else:
                            logger.info(f"    ✅ Success")
                            passed += 1
                    except Exception as e:
                        logger.error(f"    ❌ Exception: {str(e)}")
                        failed += 1
                        break
                
                # Send before test case END event to Firestore
                final_status = "failed" if failed > 0 else "success"
                try:
                    from datetime import datetime
                    from app.firestore import firestore_client
                    from app.webhook import StepExecutionSchema
                    
                    status_emoji = "✅" if final_status == "success" else "❌"
                    end_event = StepExecutionSchema(
                        step_number=0,
                        timestamp=datetime.utcnow().isoformat() + "Z",
                        agent_name=self.name,
                        session_id=getattr(self, "session_id", None),
                        user_id=getattr(self, "user_id", None),
                        tenant_id=getattr(self, "tenant_id", None),
                        test_case_id=getattr(self, "test_case_id", None),
                        event_type="before_test_case_end",
                        status=final_status,
                        thinking=f"{status_emoji} Before test case {idx + 1}/{len(all_before_tc_ids)} completed: {before_tc_data.get('summary', before_tc_id)} ({passed}/{len(proven_steps)} steps passed)"
                    )
                    
                    if firestore_client.enabled:
                        await firestore_client.save_step(end_event, [])
                except Exception as e:
                    logger.debug(f"Failed to send before_test_case_end event: {e}")
                
                if failed > 0:
                    logger.error(f"\n❌ BEFORE test case '{before_tc_id}' failed ({passed} passed, {failed} failed)")
                    logger.error("⚠️  Continuing with AI Exploration despite failure (non-blocking)")
                else:
                    logger.info(f"\n✅ BEFORE test case '{before_tc_id}' completed successfully ({passed} steps)")
            
            logger.info("\n" + "="*70)
            logger.info("✅ BEFORE TEST CASES COMPLETED")
            logger.info("="*70 + "\n")
            logger.info("🤖 Starting AI Exploration from current browser state...")
            
            # Add context to agent's memory about executed before steps
            if all_before_tc_ids:
                # Get test case names for better context
                before_names = []
                for tc_id in all_before_tc_ids:
                    tc_data = await get_test_case_data(tc_id, self.tenant_id)
                    tc_name = tc_data.get("summary", tc_id) if tc_data else tc_id
                    before_names.append(tc_name)
                
                context_message = (
                    f"🔷 IMPORTANT CONTEXT - READ CAREFULLY:\n\n"
                    f"Setup steps have ALREADY been executed before your task. These are DONE:\n"
                )
                for idx, name in enumerate(before_names, 1):
                    context_message += f"  {idx}. {name} ✅\n"
                
                context_message += (
                    f"\n🎯 CRITICAL INSTRUCTIONS FOR YOU:\n"
                    f"1. STILL CREATE A PLAN using 'planning' tool (command='create') - THIS IS MANDATORY!\n"
                    f"2. DO NOT navigate to the application - browser is already there\n"
                    f"3. DO NOT perform setup steps - they're already done\n"
                    f"4. Your task starts from the CURRENT browser state\n"
                    f"5. Create your plan for YOUR SPECIFIC TASK only\n\n"
                    f"Example: If your task is 'Update profile', create a plan like:\n"
                    f"  1. Locate profile section\n"
                    f"  2. Update fields\n"
                    f"  3. Validate changes\n\n"
                    f"DO NOT include navigation or login in your plan - that's already done!\n"
                )
                
                # Add to agent's memory as a system message
                from app.schema import Message
                self.memory.add_message(Message.system_message(context_message))
                logger.info(f"✅ Added context to agent about {len(all_before_tc_ids)} completed before test cases")
            
        except Exception as e:
            logger.error(f"Error executing before shared test cases: {e}")
            import traceback
            traceback.print_exc()
    
    async def cleanup(self):
        """Clean up E2B agent resources."""
        if self._initialized and self.sandbox:
            logger.info("Cleaning up E2B sandbox...")
            delete_sandbox(self.sandbox)
            self._initialized = False
            logger.info("E2B cleanup complete")
