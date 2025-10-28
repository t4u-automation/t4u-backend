"""E2B Sub-Agent Tool - Delegate subtasks to specialized agent"""

import asyncio
import time
from typing import Any, Optional

from pydantic import PrivateAttr

from app.e2b.tool_base import E2BToolsBase
from app.schema import AgentState, Message
from app.tool.base import ToolResult
from app.utils.logger import logger

_SUB_AGENT_DESCRIPTION = """\
Delegate a specific subtask to a specialized sub-agent that runs in the sandbox.

Use this when:
- A subtask is complex and might require multiple attempts (e.g., login, fill form, navigate menu)
- You want to isolate the subtask context to avoid polluting main conversation
- The subtask might need vision/screenshots to verify success

The sub-agent:
- Has its own isolated LLM conversation (won't bloat main agent context)
- Can use Playwright browser tools (shared browser state)
- Can take screenshots and use Claude Vision
- Returns only a summary result (success/failure + details)

Example: Instead of main agent trying login 10 times (10 steps), 
delegate to sub-agent (1 step in main context, returns "Login successful")
"""


class E2BSubAgentTool(E2BToolsBase):
    """
    Tool for delegating subtasks to a specialized sub-agent in E2B sandbox.
    Sub-agent has own LLM context and can use browser/vision tools directly.
    """

    name: str = "e2b_sub_agent"
    description: str = _SUB_AGENT_DESCRIPTION
    
    # Store reference to parent agent's tool collection and agent itself
    _parent_tool_collection: Optional[Any] = PrivateAttr(default=None)
    _parent_agent: Optional[Any] = PrivateAttr(default=None)
    
    def set_parent_tools(self, tool_collection):
        """Set reference to parent agent's tools for sharing"""
        self._parent_tool_collection = tool_collection
    
    def set_parent_agent(self, agent):
        """Set reference to parent agent for accessing current step"""
        self._parent_agent = agent
    
    parameters: dict = {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "Specific subtask to delegate (e.g., 'Login with email user@example.com and password abc123')",
            },
            "max_attempts": {
                "type": "integer",
                "description": "Maximum steps sub-agent can make (default: 100)",
                "default": 100,
            },
            "use_vision": {
                "type": "boolean",
                "description": "Whether sub-agent should use screenshots/vision (default: false)",
                "default": False,
            },
            "context": {
                "type": "string",
                "description": "Brief context about what has been done so far (e.g., 'Already logged in, currently on dashboard at /dashboard/announcements')",
            },
        },
        "required": ["task"],
    }

    _sub_agent_script_path: str = PrivateAttr(default="/tmp/sub_agent.py")

    async def execute(
        self,
        task: str,
        max_attempts: int = 100,
        use_vision: bool = False,
        context: str = None,
        **kwargs,
    ) -> ToolResult:
        """
        Execute subtask using specialized sub-agent (in-memory, reuses existing code)
        
        Args:
            task: Specific task description
            max_attempts: Max steps for sub-agent
            use_vision: Not used (kept for compatibility)
            context: Brief context about current state (provided by main agent)
        """
        if not self.sandbox:
            return self.fail_response("E2B sandbox not initialized")

        try:
            start_time = time.time()
            
            # Import agent class (reuse existing code!)
            from app.agent.toolcall import ToolCallAgent
            from app.tool import ToolCollection
            from app.tool.sub_task_complete import SubTaskComplete
            
            # Get parent session context and CURRENT step number from running agent
            parent_session_id = getattr(self, '_session_id', None)
            parent_user_id = getattr(self, '_user_id', None)
            
            # Get tenant_id and test_case_id from parent agent
            parent_tenant_id = None
            parent_test_case_id = None
            if self._parent_agent:
                parent_current_step = self._parent_agent.current_step
                parent_tenant_id = getattr(self._parent_agent, 'tenant_id', None)
                parent_test_case_id = getattr(self._parent_agent, 'test_case_id', None)
            else:
                parent_current_step = getattr(self, '_current_step', 0)
            
            # Create sub-agent with isolated context
            sub_agent = ToolCallAgent()
            sub_agent.max_steps = max_attempts
            sub_agent.state = AgentState.IDLE
            
            # CRITICAL: Start AFTER parent's current step to avoid collision!
            # Parent's step that called sub_agent will be saved with parent_current_step
            # Sub-agent starts at parent_current_step (will increment to +1 on first step)
            sub_agent.current_step = parent_current_step  # First step() call will make this +1
            
            # Use SAME session_id as parent for step queries
            # But mark with different agent_name to distinguish
            sub_agent.session_id = parent_session_id  # For step filtering!
            sub_agent.user_id = parent_user_id
            sub_agent.tenant_id = parent_tenant_id  # Inherit from parent
            sub_agent.test_case_id = parent_test_case_id  # Inherit from parent
            
            # Mark as sub-agent in Firestore (for easy filtering)
            sub_agent.name = "E2BTestOpsAI-SubAgent"
            
            # Determine which parent step we're working on (for proven step tracking)
            parent_in_progress_step = None
            if self._parent_agent and hasattr(self._parent_agent, '_step_tool_calls'):
                # Find the currently in-progress step in parent
                for step_idx in self._parent_agent._step_tool_calls.keys():
                    step_data = self._parent_agent._step_tool_calls[step_idx]
                    # If it's still a list (not converted to dict yet), it's in progress
                    if isinstance(step_data, list):
                        parent_in_progress_step = step_idx
                        break
            
            # Initialize sub-agent's tracking for the parent's in-progress step
            if parent_in_progress_step is not None:
                # Initialize tracking so sub-agent's actions get recorded
                sub_agent._step_tool_calls[parent_in_progress_step] = []
            
            # Reuse SAME browser tool instance from parent (shares browser state!)
            if self._parent_tool_collection:
                # Get the ACTUAL browser tool instance from parent
                parent_browser_tool = self._parent_tool_collection.get_tool("e2b_browser")
            else:
                # Fallback: create new (will detect existing browser)
                from app.tool.e2b.e2b_browser_tool import E2BBrowserTool
                parent_browser_tool = E2BBrowserTool(sandbox=self.sandbox)
            
            sub_agent.available_tools = ToolCollection(
                parent_browser_tool,  # SAME instance! Browser already initialized!
                SubTaskComplete()  # Sub-agent uses sub_task_complete, NOT terminate!
                # NO Terminate - that's for main agent only
                # NO e2b_sub_agent tool - prevents infinite recursion!
                # NO planning tool - sub-agent shouldn't modify parent's plan!
            )
            
            # Highly prescriptive system prompt for sub-agent
            sub_agent.system_prompt = (
                "You are a sub-agent. Focus on achieving your task goal!\n"
                "\n"
                "🚨 TASK FOCUS RULES:\n"
                "✅ DO: Try different approaches to achieve the task goal\n"
                "✅ DO: Use semantic locators, screenshots, different element indices\n"
                "✅ DO: Retry if first approach doesn't work\n"
                "❌ DON'T: Do things beyond the task scope\n"
                "❌ DON'T: Explore features not related to your task\n"
                "❌ DON'T: Click on items to extract details unless explicitly asked\n"
                "- When task goal achieved → call sub_task_complete() IMMEDIATELY\n"
                "- Example: Task 'validate news section present' → Use get_headings() or get_by_text('news'), see it exists, DONE ✅\n"
                "- Example: Task 'validate news section present' → Don't click each news article to extract details ❌\n"
                "- Example: Task 'extract 3 news articles' → Then you click and extract ✅\n"
                "\n"
                "MANDATORY WORKFLOW - FOLLOW EXACTLY:\n"
                "\n"
                "YOUR VERY FIRST ACTION: Use the RIGHT SEMANTIC LOCATOR for your task:\n"
                "- If task mentions 'announcements/posts/articles': Try get_by_role(role='article') OR get_by_text(search_text='announcement')\n"
                "- If looking for items in a list: get_by_role(role='listitem')\n"
                "- If looking for specific text/keyword: get_by_text(search_text='the keyword from your task')\n"
                "- To see titles: get_headings()\n"
                "- For navigation: get_buttons() or get_links()\n"
                "\n"
                "🎯 ADAPT TO YOUR TASK:\n"
                "- Read your task carefully\n"
                "- Choose the semantic locator that matches what you're looking for\n"
                "- Try multiple approaches if first doesn't work (get_by_role('article'), then get_by_text('announcement'), then get_by_role('listitem'))\n"
                "\n"
                "DO NOT use get_elements() first - it returns ALL elements!\n"
                "DO use specific semantic locators matched to your task!\n"
                "\n"
                "AFTER get_elements():\n"
                "STEP 2: Find announcement/card/item elements in the list\n"
                "STEP 3: CLICK the first item to open it (use click_element with index)\n"
                "STEP 4: get_elements() to see what's on the detail page\n"
                "STEP 5: Use assertions to validate final state\n"
                "STEP 6: go_back to return to list\n"
                "STEP 6: CLICK next item\n"
                "STEP 7: Extract from opened view\n"
                "STEP 8: Repeat until all items extracted\n"
                "STEP 9: sub_task_complete() with all collected data\n"
                "\n"
                "EXAMPLE WORKFLOW (adapt to YOUR specific task):\n"
                "If task = 'Extract 3 announcements':\n"
                "  Step 1: get_by_text(search_text='announcement') → Find announcement elements\n"
                "  OR: get_by_role(role='article') → If announcements are article elements\n"
                "  → Found 3 items at [0], [1], [2]\n"
                "  Step 2: click_element(0) → Opens first\n"
                "  Step 3: get_headings() → See title\n"
                "  Step 4: Use assertions to validate content\n"
                "  Step 5: go_back\n"
                "  Step 6-9: Repeat for items [1] and [2]\n"
                "  Step 10: sub_task_complete(summary='3 announcements extracted')\n"
                "\n"
                "🎯 KEY PRINCIPLE: Match your locator to your TASK KEYWORDS\n"
                "- Task says 'announcements'? → get_by_text(search_text='announcement')\n"
                "- Task says 'products'? → get_by_text(search_text='product')\n"
                "- Task says 'cards'? → get_by_role(role='article') or get_by_role(role='listitem')\n"
                "\n"
                "🚨 BANNED ACTIONS:\n"
                "- ❌ Scrolling more than twice (click items instead!)\n"
                "- ❌ Calling get_elements() more than 3 times total\n"
                "- ❌ Using get_page_content (use get_elements + click instead!)\n"
                "\n"
                "- Extract data from CURRENT opened page (after clicking an item)\n"
                "- Get text content that's visible but not in element list\n"
                "- Parse data from a detail view\n"
                "\n"
                "🔧 USE ASSERTIONS FOR VALIDATION:\n"
                "- assert_element_visible(search_text='...')\n"
                "- assert_count_equals(search_text='article', expected_count=5)\n"
                "\n"
                "\n"
                "If you've done 15+ steps: STOP and call sub_task_complete() with whatever you have!\n"
            )
            
            # Directive next_step_prompt with semantic locators
            sub_agent.next_step_prompt = (
                "Read your task CAREFULLY - do ONLY what it asks!\n"
                "\n"
                "If task says 'validate X is present' → Check it exists, then DONE\n"
                "If task says 'extract details from X' → Then click and extract\n"
                "\n"
                "Use semantic locators (get_buttons, get_links, get_inputs, get_headings)\n"
                "\n"
                "STOP immediately when task goal is met!\n"
                "Don't explore, don't extract extra data, don't click unnecessary things"
            )
            
            # Increase observation limit so sub-agent can see full element lists
            # (needed to find announcement cards that might be at index 50, 100, etc.)
            sub_agent.max_observe = 10000  # Allow seeing more elements
            
            # Give sub-agent context about current state
            context_messages = []
            
            # If main agent provided explicit context, use it (preferred!)
            if context:
                context_msg = Message.user_message(
                    f"🚨 CONTEXT FROM MAIN AGENT:\n{context}\n\n"
                    f"Use get_elements() to see current page state, then complete your task."
                )
                context_messages.append(context_msg)
            else:
                # Fallback: try to detect current state from browser
                auto_context = await self._create_context_message(parent_browser_tool)
                if auto_context:
                    context_messages.append(auto_context)
            
            # Start with context message(s)
            sub_agent.messages = context_messages
            
            # Run sub-agent with task (skip cleanup - shares browser with main!)
            
            # Track if sub-agent called terminate (state gets reset by context manager)
            did_finish = False
            original_handle_special = sub_agent._handle_special_tool
            
            async def track_termination(name, result, **kwargs):
                nonlocal did_finish
                if name.lower() == "sub_task_complete":
                    did_finish = True
                    # Don't call original handler - sub_task_complete isn't a special tool
                    # Just mark as finished
                    sub_agent.state = AgentState.FINISHED
                    return
                return await original_handle_special(name, result, **kwargs)
            
            sub_agent._handle_special_tool = track_termination
            
            # Pass skip_cleanup=True to prevent browser shutdown!
            result = await sub_agent.run(task, skip_cleanup=True)
            
            elapsed = time.time() - start_time
            
            # Get final step count (might be reset by context manager)
            steps_used = sub_agent.current_step
            
            # ALWAYS update parent step counter, even if sub-agent failed
            # This prevents step number collisions
            if self._parent_agent and steps_used > 0:
                self._parent_agent.current_step = steps_used
            elif self._parent_agent:
                # If steps_used is 0 (wrong!), at least increment parent by 1
                self._parent_agent.current_step += 1
                logger.warning(f"⚠️  Sub-agent reported 0 steps, incrementing parent to {self._parent_agent.current_step}")
            
            # Transfer sub-agent's execution history to parent
            if self._parent_agent and hasattr(sub_agent, '_execution_history') and sub_agent._execution_history:
                # Append all sub-agent's execution history to parent
                self._parent_agent._execution_history.extend(sub_agent._execution_history)
                logger.debug(f"✅ Transferred {len(sub_agent._execution_history)} steps from sub-agent execution history")
            
            # Transfer sub-agent's proven steps to parent agent
            if self._parent_agent and hasattr(sub_agent, '_step_tool_calls') and sub_agent._step_tool_calls:
                # Merge sub-agent's proven steps into parent's tracking
                transferred_count = 0
                for step_idx, step_data in sub_agent._step_tool_calls.items():
                    if step_idx in self._parent_agent._step_tool_calls:
                        parent_data = self._parent_agent._step_tool_calls[step_idx]
                        # If parent data is still a list (in progress), merge the lists
                        if isinstance(parent_data, list) and isinstance(step_data, list):
                            # Merge: parent's actions + sub-agent's actions
                            self._parent_agent._step_tool_calls[step_idx] = parent_data + step_data
                            transferred_count += len(step_data)
                    else:
                        # Step doesn't exist in parent yet, just copy it
                        self._parent_agent._step_tool_calls[step_idx] = step_data
                        transferred_count += 1
            
            # Check if successful (called sub_task_complete())
            if did_finish:
                # Extract the ACTUAL RESULT from sub_task_complete tool call
                summary = "Task completed"
                if sub_agent.messages:
                    # Look for the sub_task_complete tool call to get the actual summary
                    for msg in reversed(sub_agent.messages):
                        if msg.role == "assistant" and msg.tool_calls:
                            for tool_call in msg.tool_calls:
                                if tool_call.function.name == "sub_task_complete":
                                    # Extract the summary argument from the tool call
                                    import json
                                    try:
                                        args = json.loads(tool_call.function.arguments) if isinstance(tool_call.function.arguments, str) else tool_call.function.arguments
                                        if 'summary' in args:
                                            summary = args['summary']
                                            break
                                    except Exception as e:
                                        logger.warning(f"Failed to parse sub_task_complete arguments: {e}")
                                        pass
                            if summary != "Task completed":
                                break
                
                # Clean, compact result message
                result_msg = f"✅ Sub-agent completed ({steps_used} steps, {elapsed:.1f}s)\n{summary[:200]}"
                
                return self.success_response(result_msg)
            else:
                # Sub-agent ran out of steps without calling terminate()
                logger.warning(f"⚠️  Sub-agent used {steps_used} steps but didn't complete (state={sub_agent.state})")
                return self.fail_response(
                    f"❌ Sub-agent used {steps_used} steps without completing task\n"
                    f"Final state: {sub_agent.state}\n"
                    f"Last result: {result[:500]}"
                )

        except Exception as e:
            logger.error(f"Sub-agent error: {e}")
            import traceback
            traceback.print_exc()
            return self.fail_response(f"Sub-agent execution error: {e}")
    
    async def _create_context_message(self, browser_tool):
        """Create a brief context message for sub-agent about current browser state"""
        try:
            # Get current page info
            result = await browser_tool.execute(action="get_elements")
            
            # Parse the result to extract URL
            if result and "URL:" in result:
                lines = result.split('\n')
                url = ""
                title = ""
                
                for line in lines:
                    if line.startswith('URL:'):
                        url = line.replace('URL:', '').strip()
                    elif line.startswith('Title:'):
                        title = line.replace('Title:', '').strip()
                
                if url:
                    context = (
                        f"🚨 IMPORTANT CONTEXT:\n"
                        f"The browser is ALREADY on the page: {url}\n"
                        f"Page title: {title}\n"
                        f"\n"
                        f"DO NOT navigate to a different URL unless your task explicitly requires it!\n"
                        f"The previous workflow already navigated here.\n"
                        f"Just use get_elements() to see what's on THIS page, then complete your task.\n"
                        f"\n"
                        f"Current page is ready - start working on it immediately."
                    )
                    
                    # Use USER message (stronger than system message)
                    return Message.user_message(context)
        except Exception as e:
            logger.debug(f"Error creating context message: {e}")
        
        return None
    
    def _get_parent_tools(self):
        """Get tools from parent agent to share browser state"""
        # CRITICAL: Don't create new browser tool - it will start a new browser!
        # Instead, we need to get the EXISTING browser tool instance from parent
        
        # For now, create one but mark it to reuse existing browser server
        from app.tool.e2b.e2b_browser_tool import E2BBrowserTool
        
        browser_tool = E2BBrowserTool(sandbox=self.sandbox)
        # The browser tool will detect the existing server is running and reuse it
        # because _browser_initialized flag is checked in _ensure_browser_server
        
        return {
            "e2b_browser": browser_tool
        }

