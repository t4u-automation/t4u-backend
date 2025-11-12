import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import Field, PrivateAttr

from app.agent.base import BaseAgent
from app.config import WORKSPACE_ROOT
from app.exceptions import TokenLimitExceeded
from app.firestore import firestore_client
from app.logger import logger
from app.prompt.toolcall import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.schema import TOOL_CHOICE_TYPE, AgentState, Message, ToolCall, ToolChoice
from app.tool import CreateChatCompletion, Terminate, ToolCollection
from app.webhook import StepExecutionSchema

TOOL_CALL_REQUIRED = "Tool calls required but none provided"


class ToolCallAgent(BaseAgent):
    """
    Base agent class for handling tool/function calls with enhanced abstraction.
    Implements the Think-Act (ReAct) pattern with tool execution.
    """

    name: str = "toolcall"
    description: str = "an agent that can execute tool calls."

    system_prompt: str = SYSTEM_PROMPT
    next_step_prompt: str = NEXT_STEP_PROMPT

    available_tools: ToolCollection = ToolCollection(
        CreateChatCompletion(), Terminate()
    )
    tool_choices: TOOL_CHOICE_TYPE = ToolChoice.AUTO  # type: ignore
    special_tool_names: List[str] = Field(default_factory=lambda: [Terminate().name])

    tool_calls: List[ToolCall] = Field(default_factory=list)
    _current_base64_image: Optional[str] = None
    _current_thinking: Optional[str] = None  # Store thinking from current turn
    _current_step_timestamp: Optional[str] = None  # Store timestamp for current step (for consistent doc_id)
    _step_start_message_index: Dict[int, int] = PrivateAttr(default_factory=dict)  # Track where each plan step starts in message history
    _step_tool_calls: Dict[int, List[Dict]] = PrivateAttr(default_factory=dict)  # Track tool calls for each step (for replay)
    _last_element_list: Optional[List[Dict]] = PrivateAttr(default=None)  # Store last seen element list for metadata enrichment
    _pending_tool_display: List[Dict] = PrivateAttr(default_factory=list)  # Store tool calls for combined display with results
    _execution_history: List[Dict] = PrivateAttr(default_factory=list)  # Track ALL steps (thinking + action + result) for AI analysis

    max_steps: int = 30
    max_observe: Optional[Union[int, bool]] = None

    async def step(self) -> str:
        """Execute a single step: think and act (ReAct pattern)."""
        should_act = await self.think()
        if not should_act:
            return "Thinking complete - no action needed"
        return await self.act()

    async def think(self) -> bool:
        """Process current state and decide next actions using tools"""
        import time

        think_start = time.time()

        # Robust truncation: Validate and keep only complete sequences
        if len(self.messages) > 80:
            logger.warning(
                f"⚠️ Message history has {len(self.messages)} messages - truncating to prevent errors"
            )

            original_len = len(self.messages)
            
            # Strategy: Find a point where we can start with a complete assistant→tool(s)→user sequence
            # Validate that all tool_call_ids match up
            target_idx = max(0, len(self.messages) - 50)
            
            for start_idx in range(target_idx, len(self.messages)):
                msg = self.messages[start_idx]
                
                # Try starting at each user message
                if msg.role == "user" and not getattr(msg, 'tool_call_id', None):
                    # Validate the following sequence
                    valid = True
                    i = start_idx
                    
                    while i < len(self.messages):
                        current = self.messages[i]
                        
                        if current.role == "assistant" and hasattr(current, 'tool_calls') and current.tool_calls:
                            # Collect tool_call_ids from this assistant message
                            tool_call_ids = {tc.id for tc in current.tool_calls}
                            
                            # Check that all following tool messages reference these IDs
                            j = i + 1
                            while j < len(self.messages) and self.messages[j].role == "tool":
                                tool_msg = self.messages[j]
                                tc_id = getattr(tool_msg, 'tool_call_id', None)
                                if tc_id and tc_id not in tool_call_ids:
                                    # Orphaned tool result!
                                    valid = False
                                    break
                                j += 1
                            
                            if not valid:
                                break
                            i = j
                        else:
                            i += 1
                    
                    if valid:
                        # Found a valid starting point
                        self.messages = self.messages[start_idx:]
                    logger.info(
                            f"✅ Truncated from {original_len} to {len(self.messages)} messages (started at validated user message {start_idx})"
                    )
                    break
            else:
                # No valid point found - keep last 30 and hope for the best
                self.messages = self.messages[-30:]
                logger.warning(
                    f"⚠️ No valid truncation point found - kept last 30 messages"
                )

        if self.next_step_prompt:
            user_msg = Message.user_message(self.next_step_prompt)
            self.messages += [user_msg]

        logger.info(
            f"🤔 Starting think phase... ({len(self.messages)} messages in history)"
        )

        try:
            # Get response with tool options
            response = await self.llm.ask_tool(
                messages=self.messages,
                system_msgs=(
                    [Message.system_message(self.system_prompt)]
                    if self.system_prompt
                    else None
                ),
                tools=self.available_tools.to_params(),
                tool_choice=self.tool_choices,
            )
        except ValueError:
            raise
        except Exception as e:
            # Check if this is a RetryError containing TokenLimitExceeded
            if hasattr(e, "__cause__") and isinstance(e.__cause__, TokenLimitExceeded):
                token_limit_error = e.__cause__
                logger.error(
                    f"🚨 Token limit error (from RetryError): {token_limit_error}"
                )
                self.memory.add_message(
                    Message.assistant_message(
                        f"Maximum token limit reached, cannot continue execution: {str(token_limit_error)}"
                    )
                )
                self.state = AgentState.FINISHED
                return False
            raise

        self.tool_calls = tool_calls = (
            response.tool_calls if response and response.tool_calls else []
        )
        content = response.content if response and response.content else ""
        
        # Store thinking content for this turn
        self._current_thinking = content if content else None
        if self._current_thinking:
            logger.debug(f"💭 Captured thinking content: {len(self._current_thinking)} chars")
        else:
            logger.debug(f"💭 No thinking content in this response (tool calls only)")

        # Log thinking duration and results
        think_duration = time.time() - think_start
        logger.info(f"✅ Think phase completed in {think_duration:.1f}s")

        # Check if response was truncated (DISABLED - breaks conversation structure)
        # TODO: Implement proper guidance that doesn't break message sequences
        if (
            hasattr(self.llm, "last_response_truncated")
            and self.llm.last_response_truncated
        ):
            logger.warning(
                "⚠️ Truncation detected (guidance disabled to prevent conversation corruption)"
            )
            # Just log it - don't inject messages that break tool_call sequences
            self.llm.last_response_truncated = False

        # Clean, structured logging
        step_log = {
            "step": self.current_step,
            "agent": self.name,
            "thinking": content[:200] if content and len(content) > 200 else content,
            "tool_calls": []
        }

        if tool_calls:
            for tc in tool_calls:
                args = (
                    json.loads(tc.function.arguments)
                    if isinstance(tc.function.arguments, str)
                    else tc.function.arguments
                )
                step_log["tool_calls"].append({
                    "tool_name": tc.function.name,
                    "arguments": args
                })
        
        # Tabular format output - header and thinking first
        agent_type = "Main Agent" if "SubAgent" not in self.name else "Sub-Agent"
        
        print(f"\n┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓")
        print(f"┃ Step {self.current_step:>3}/{self.max_steps:<3}     ┃ {agent_type:<48} ┃")
        print(f"┣━━━━━━━━━━━━━━━╋━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫")
        
        if content:
            # Show full thinking in dedicated row
            print(f"┃ 💭 Thinking    ┃                                                  ┃")
            print(f"┣━━━━━━━━━━━━━━━╋━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫")
            # Split thinking into multiple lines if needed
            thinking_lines = []
            for i in range(0, len(content), 63):
                thinking_lines.append(content[i:i+63])
            for line in thinking_lines[:3]:  # Max 3 lines
                print(f"┃                ┃ {line:<48} ┃")
        
        # Store tool calls for combined display in act()
        self._pending_tool_display = step_log['tool_calls'] if tool_calls else []

        try:
            if response is None:
                raise RuntimeError("No response received from the LLM")

            # Handle different tool_choices modes
            if self.tool_choices == ToolChoice.NONE:
                if tool_calls:
                    logger.warning(
                        f"🤔 Hmm, {self.name} tried to use tools when they weren't available!"
                    )
                if content:
                    self.memory.add_message(Message.assistant_message(content))
                    return True
                return False

            # Create and add assistant message
            assistant_msg = (
                Message.from_tool_calls(content=content, tool_calls=self.tool_calls)
                if self.tool_calls
                else Message.assistant_message(content)
            )

            self.memory.add_message(assistant_msg)

            if self.tool_choices == ToolChoice.REQUIRED and not self.tool_calls:
                return True  # Will be handled in act()

            # For 'auto' mode, continue with content if no commands but content exists
            if self.tool_choices == ToolChoice.AUTO and not self.tool_calls:
                return bool(content)

            return bool(self.tool_calls)
        except Exception as e:
            logger.error(f"🚨 Oops! The {self.name}'s thinking process hit a snag: {e}")
            self.memory.add_message(
                Message.assistant_message(
                    f"Error encountered while processing: {str(e)}"
                )
            )
            return False

    async def act(self) -> str:
        """Execute tool calls and handle their results"""
        # Prepare webhook data
        tool_calls_data = []
        tool_results_data = []
        screenshots = []

        # 🔥 IMMEDIATELY save thinking + planned tool calls to Firestore BEFORE execution
        # This allows users to see what the agent is planning in real-time
        if self.tool_calls:
            # Generate timestamp once for this step (so both saves use same doc_id)
            self._current_step_timestamp = datetime.utcnow().isoformat() + "Z"
            
            # Prepare tool calls data for immediate save
            immediate_tool_calls_data = []
            for command in self.tool_calls:
                args = json.loads(command.function.arguments or "{}")
                immediate_tool_calls_data.append(
                    {"tool_name": command.function.name, "arguments": args}
                )
            
            # Save with status="executing" to indicate tools haven't run yet
            await self._save_step_to_firestore_immediately(
                immediate_tool_calls_data, [], []  # Empty results and screenshots
            )
            logger.debug(f"💾 Saved thinking + planned tool calls to Firestore BEFORE execution")

        if not self.tool_calls:
            if self.tool_choices == ToolChoice.REQUIRED:
                raise ValueError(TOOL_CALL_REQUIRED)

            # Return last message content if no tool calls
            last_msg = self.memory.messages[-1] if self.memory.messages else None
            return last_msg.content if last_msg and last_msg.content else ""

        results = []
        
        # Display tool calls if any are pending
        if self._pending_tool_display:
            # Add section header for tools
            print(f"┣━━━━━━━━━━━━━━━╋━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫")
            print(f"┃ 🔧 Tool Calls   ┃                                                  ┃")
            
            for i, tc in enumerate(self._pending_tool_display):
                print(f"┣━━━━━━━━━━━━━━━╋━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫")
                
                tool_name = tc['tool_name']
                args = tc['arguments']
                
                # Format tool name
                print(f"┃ Tool           ┃ {tool_name:<48} ┃")
                
                # Format arguments (key ones only)
                if 'action' in args:
                    action = args['action']
                    print(f"┃ Action         ┃ {action:<48} ┃")
                
                # Show relevant args based on action
                for key, value in list(args.items())[:3]:  # Max 3 args
                    if key != 'action':
                        value_str = str(value)[:43]
                        print(f"┃ {key:<14} ┃ {value_str:<48} ┃")
        
        for command in self.tool_calls:
            # Record tool call
            args = json.loads(command.function.arguments or "{}")
            
            # For planning tool: Inject plan_id if missing (uses active plan)
            if command.function.name == "planning" and "plan_id" not in args:
                # Get the active plan_id from the planning tool
                planning_tool = self.available_tools.get_tool("planning")
                if planning_tool and hasattr(planning_tool, '_current_plan_id') and planning_tool._current_plan_id:
                    args["plan_id"] = planning_tool._current_plan_id
                    logger.debug(f"✅ Injected active plan_id: {args['plan_id']}")
                else:
                    logger.warning(
                        f"⚠️ Planning tool call missing plan_id and no active plan! Args: {args}"
                    )
            
            # Track when steps start (in_progress) and complete
            if command.function.name == "planning" and args.get("command") == "mark_step":
                step_idx = args.get("step_index")
                step_status = args.get("step_status")
                
                if step_status == "in_progress" and step_idx is not None:
                    # Record where this step starts in message history
                    self._step_start_message_index[step_idx] = len(self.messages)
                    # Initialize tool calls tracker for this step
                    self._step_tool_calls[step_idx] = []
                    logger.debug(f"📍 Step {step_idx} starts at message index {len(self.messages)}")
            
            # Track non-planning tool calls for the current in-progress step
            # Only track ACTION tools, not information-gathering tools
            if command.function.name != "planning":
                # Determine if this is an action tool (for replay) or info tool (AI only)
                is_action_tool = self._is_action_tool(command.function.name, args)
                
                if is_action_tool:
                    # Enrich action with element metadata for reliable replay
                    enriched_args = args.copy()
                    
                    # For click_element or input_text, add element metadata from last seen list
                    if command.function.name == "e2b_browser":
                        action = args.get("action", "")
                        if action in ["click_element", "input_text"] and "index" in args:
                            index = args.get("index")
                            if self._last_element_list and 0 <= index < len(self._last_element_list):
                                elem = self._last_element_list[index]
                                enriched_args["_element_metadata"] = {
                                    "text": elem.get("text", "")[:100],
                                    "id": elem.get("id", ""),
                                    "class": elem.get("class", ""),
                                    "tag": elem.get("tag", ""),
                                    "type": elem.get("type", "")
                                }
                                logger.debug(f"🏷️  Enriched {action} with element metadata: {enriched_args['_element_metadata']}")
                    
                    # Find which step is currently in progress
                    for step_idx in self._step_tool_calls.keys():
                        step_data = self._step_tool_calls[step_idx]
                        # Only append if it's still a list (not converted to dict yet)
                        if isinstance(step_data, list):
                            # Add this tool call to the step's proven actions
                            step_data.append({
                                "tool_name": command.function.name,
                                "arguments": enriched_args
                            })
                            logger.debug(f"📝 Recorded ACTION: {command.function.name} for step {step_idx}")
                else:
                    logger.debug(f"⏭️  Skipped INFO tool: {command.function.name} (not needed for replay)")
            
            tool_calls_data.append(
                {"tool_name": command.function.name, "arguments": args}
            )
            # Reset base64_image for each tool call
            self._current_base64_image = None

            result = await self.execute_tool(command)

            # Extract element list from browser results for metadata enrichment
            if command.function.name == "e2b_browser":
                action = args.get("action", "")
                # Parse element list from navigate_to, click_element, or get_elements results
                if action in ["navigate_to", "click_element", "get_elements"]:
                    try:
                        result_str = str(result)
                        # Extract elements from response (they're in a specific format)
                        if "Elements:" in result_str or "Page Elements" in result_str:
                            # Parse element list from result
                            elements = self._parse_element_list_from_result(result_str)
                            if elements:
                                self._last_element_list = elements
                                logger.debug(f"📋 Stored {len(elements)} elements for metadata enrichment")
                    except Exception as e:
                        logger.debug(f"Failed to extract element list: {e}")

            # For sub-agent results, NEVER truncate (contains critical extracted data)
            # For other tools, apply max_observe truncation if set
            if self.max_observe and command.function.name != "e2b_sub_agent":
                result = result[: self.max_observe]

            # Add result to same table (after tool call)
            result_str = str(result)
            
            # Check for errors in multiple ways
            has_error = (hasattr(result, 'error') and result.error) or result_str.startswith("Error:")
            result_success = not has_error
            
            # Add separator before result
            print(f"┣━━━━━━━━━━━━━━━╋━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫")
            
            status = "✅ Success" if result_success else "❌ Error"
            print(f"┃ Result         ┃ {status:<48} ┃")
            
            if not result_success:
                # Show error message (remove "Error: " prefix if present)
                error_msg = result_str.replace("Error: ", "", 1) if result_str.startswith("Error:") else result_str
                error_lines = error_msg.split('\n')[:2]  # Max 2 lines
                for line in error_lines:
                    line_preview = line.strip()[:48]
                    if line_preview:
                        print(f"┃ Error          ┃ {line_preview:<48} ┃")
            elif len(result_str) < 200 and result_str.strip():
                # Show result in table rows (split if multi-line)
                lines = result_str.split('\n')[:2]  # Max 2 lines
                for line in lines:
                    line_preview = line.strip()[:48]
                    if line_preview:
                        print(f"┃ Output         ┃ {line_preview:<48} ┃")

            # Record tool result
            # For sub-agent, preserve FULL result (contains extracted data summary)
            # For other tools, truncate to save space
            if command.function.name == "e2b_sub_agent":
                output = result  # Keep full result!
            else:
                output = result[:500]  # Truncate to first 500 chars
            
            tool_result = {
                    "tool_name": command.function.name,
                    "success": (
                        not result.startswith("Error")
                        if isinstance(result, str)
                        else True
                    ),
                "output": output,
                }
            tool_results_data.append(tool_result)

            # Add tool response to memory
            tool_msg = Message.tool_message(
                content=result,
                tool_call_id=command.id,
                name=command.function.name,
                base64_image=self._current_base64_image,
            )
            self.memory.add_message(tool_msg)
            results.append(result)
            
            # Track in execution history (for AI proven steps analysis)
            # Screenshots are already removed at source (browser script)
            agent_type = "Main Agent" if "SubAgent" not in self.name else "Sub-Agent"
            self._execution_history.append({
                "step_number": self.current_step,
                "agent": agent_type,
                "thinking": self._current_thinking or "",
                "tool_call": {
                    "tool_name": command.function.name,
                    "arguments": args
                },
                "result_preview": result_str[:200],  # For quick viewing
                "result_full": result_str,  # FULL result - no truncation, no screenshots
                "success": result_success,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

        # No screenshots anymore
        screenshots = []
        
        # Track completed steps for proven_steps (saved at session end)
        await self._track_proven_steps(tool_calls_data, tool_results_data)
        
        # Close the table after all tools and results
        print(f"┗━━━━━━━━━━━━━━━┻━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛")
        
        # Clear pending tool display
        self._pending_tool_display = []
        
        # DISABLED: Condensation breaks message structure and causes tool_call_id errors
        # await self._condense_completed_steps(tool_calls_data, tool_results_data)
        
        # 🔥 Save to Firestore IMMEDIATELY after ALL tools complete (not inside loop!)
        await self._save_step_to_firestore_immediately(
            tool_calls_data, tool_results_data, screenshots
        )
        
        # Clear timestamp for next step
        self._current_step_timestamp = None

        # Send webhook
        await self._send_webhook_data(tool_calls_data, tool_results_data, screenshots)

        return "\n\n".join(results)

    def _parse_element_list_from_result(self, result_str: str) -> List[Dict]:
        """Parse element list from browser tool result for metadata enrichment"""
        elements = []
        try:
            lines = result_str.split('\n')
            for line in lines:
                # Match lines like: [0] button type=button text='Sign In' id='login-btn'
                if line.strip().startswith('[') and ']' in line:
                    parts = line.strip().split(']', 1)
                    if len(parts) == 2:
                        try:
                            index = int(parts[0].strip('['))
                            elem_info = parts[1].strip()
                            
                            # Parse element attributes
                            elem = {"index": index}
                            
                            # Extract tag
                            first_space = elem_info.find(' ')
                            if first_space > 0:
                                elem["tag"] = elem_info[:first_space]
                            
                            # Extract text='...'
                            if "text='" in elem_info:
                                text_start = elem_info.find("text='") + 6
                                text_end = elem_info.find("'", text_start)
                                if text_end > text_start:
                                    elem["text"] = elem_info[text_start:text_end]
                            
                            # Extract id='...'
                            if "id='" in elem_info:
                                id_start = elem_info.find("id='") + 4
                                id_end = elem_info.find("'", id_start)
                                if id_end > id_start:
                                    elem["id"] = elem_info[id_start:id_end]
                            
                            # Extract class='...'
                            if "class='" in elem_info:
                                class_start = elem_info.find("class='") + 7
                                class_end = elem_info.find("'", class_start)
                                if class_end > class_start:
                                    elem["class"] = elem_info[class_start:class_end]
                            
                            elements.append(elem)
                        except:
                            pass
        except Exception as e:
            logger.debug(f"Element list parsing error: {e}")
        
        return elements
    
    def _is_action_tool(self, tool_name: str, args: dict) -> bool:
        """Determine if a tool call is an ACTION (for replay) or INFO (AI decision-making only)
        
        Action tools: Modify state, interact with page (navigate, click, fill)
        Info tools: Gather data for AI (get_elements, get_by_role, vision)
        """
        # e2b_browser actions
        if tool_name == "e2b_browser":
            action = args.get("action", "")
            
            # ACTION tools (needed for replay)
            action_tools = {
                "navigate_to",
                "click",
                "fill",
                "send_keys",
                "scroll_down",
                "scroll_up",
                "scroll_to_text",
                "select_dropdown_option",
                "click_coordinates",
                "drag_drop",
                "go_back",
                "switch_tab",
                "close_tab",
                # Assertions - critical for test validation
                "assert_element_visible",
                "assert_element_hidden",
                "assert_text_contains",
                "assert_url_contains",
                "assert_count_equals",
                "assert_has_value",
                # NOTE: "wait" is intentionally excluded - fixed waits are unreliable for replay
                # Playwright has built-in smart auto-waiting that adapts to app performance
            }
            
            # INFO tools (not needed for replay - just for AI to make decisions)
            info_tools = {
                "get_elements",      # Gets element list for AI to decide
                "get_page_content",  # Gets HTML for AI to analyze
                "get_dropdown_options"  # For AI to see options
            }
            
            return action in action_tools
        
        # e2b_vision is always INFO (AI needs to see, replay doesn't)
        if tool_name == "e2b_vision":
            return False
        
        # e2b_shell, e2b_files - if we add them back, treat as actions
        if tool_name in ["e2b_shell", "e2b_files"]:
            return True
        
        # Other tools - default to not recording (safe)
        return False

    async def _track_proven_steps(self, tool_calls_data, tool_results_data):
        """Track proven steps metadata (for saving at session end)"""
        try:
            # Check if any step was marked as completed
            for tool_call in tool_calls_data:
                if (tool_call.get("tool_name") == "planning" and 
                    tool_call.get("arguments", {}).get("command") == "mark_step" and
                    tool_call.get("arguments", {}).get("step_status") == "completed"):
                    
                    step_idx = tool_call.get("arguments", {}).get("step_index")
                    
                    # Store step description for later saving
                    if step_idx in self._step_tool_calls and self._step_tool_calls[step_idx]:
                        # Get step description from planning tool result
                        step_description = f"Step {step_idx}"
                        for result in tool_results_data:
                            if result.get("tool_name") == "planning":
                                output = result.get("output", "")
                                lines = output.split('\n')
                                for line in lines:
                                    if f"{step_idx}." in line and "[✓]" in line:
                                        # Extract: "0. [✓] Navigate to yourhddev.web.app"
                                        step_description = line.split('] ', 1)[-1] if ']' in line else line
                                        break
                        
                        # Store description with tool calls (save happens at session end)
                        self._step_tool_calls[step_idx] = {
                            'tool_calls': self._step_tool_calls[step_idx],
                            'description': step_description
                        }
                        logger.debug(f"📝 Tracked proven step {step_idx}: {step_description}")
                    
                    # Clean up start index (no longer needed)
                    if step_idx in self._step_start_message_index:
                        del self._step_start_message_index[step_idx]
                        
        except Exception as e:
            logger.debug(f"Error tracking proven steps: {e}")
            pass
    
    async def _save_all_proven_steps(self):
        """Save all proven steps (main agent + sub-agents) to Firestore at session end"""
        try:
            from app.firestore import firestore_client
            
            session_id = getattr(self, "session_id", None)
            if not session_id or not firestore_client.enabled:
                return
            
            # Only main agent should save (sub-agents transfer their steps to main agent)
            if "SubAgent" in self.name:
                logger.debug("Skipping proven steps save for sub-agent (should be saved by main agent)")
                return
            
            if not self._step_tool_calls:
                logger.debug("No proven steps to save")
                return
            
            # Save each proven step
            for step_idx, step_data in self._step_tool_calls.items():
                if isinstance(step_data, dict) and 'tool_calls' in step_data:
                    await firestore_client.add_proven_step(
                        session_id=session_id,
                        step_index=step_idx,
                        step_description=step_data['description'],
                        tool_calls=step_data['tool_calls']
                    )
                    logger.info(f"✅ Saved proven step {step_idx}: {step_data['description']}")
                    
        except Exception as e:
            logger.error(f"Error saving proven steps: {e}")
            import traceback
            traceback.print_exc()

    async def _condense_completed_steps(self, tool_calls_data, tool_results_data):
        """Condense message history for completed plan steps to save tokens"""
        try:
            # Check if any step was marked as completed
            for tool_call in tool_calls_data:
                if (tool_call.get("tool_name") == "planning" and 
                    tool_call.get("arguments", {}).get("command") == "mark_step" and
                    tool_call.get("arguments", {}).get("step_status") == "completed"):
                    
                    step_idx = tool_call.get("arguments", {}).get("step_index")
                    
                    # Save proven steps to Firestore for replay
                    if step_idx in self._step_tool_calls and self._step_tool_calls[step_idx]:
                        # Get step description from planning tool result
                        step_description = f"Step {step_idx}"
                        for result in tool_results_data:
                            if result.get("tool_name") == "planning":
                                output = result.get("output", "")
                                lines = output.split('\n')
                                for line in lines:
                                    if f"{step_idx}." in line and "[✓]" in line:
                                        # Extract: "0. [✓] Navigate to yourhddev.web.app"
                                        step_description = line.split('] ', 1)[-1] if ']' in line else line
                                        break
                
                # Save to Firestore
                session_id = getattr(self, "session_id", None)
                if session_id:
                    await firestore_client.add_proven_step(
                        session_id=session_id,
                        step_index=step_idx,
                        step_description=step_description,
                        tool_calls=self._step_tool_calls[step_idx]
                    )
                
                # Clear this step's tool calls
                del self._step_tool_calls[step_idx]
                
                if step_idx in self._step_start_message_index:
                    start_idx = self._step_start_message_index[step_idx]
                    current_idx = len(self.messages)
                    
                    # Calculate messages for this step
                    step_message_count = current_idx - start_idx
                    
                    if step_message_count > 5:  # Only condense if there are many messages
                        # Strategy: Shorten tool result content but keep message structure
                        # Don't break assistant→tool→user sequences
                        
                        tokens_saved = 0
                        for i in range(start_idx, current_idx):
                            msg = self.messages[i]
                            
                            # Shorten tool result content to save tokens
                            if msg.role == "tool" and hasattr(msg, 'content') and len(msg.content) > 200:
                                original_len = len(msg.content)
                                # Keep first 200 chars as summary
                                msg.content = msg.content[:200] + "...[condensed]"
                                tokens_saved += (original_len - len(msg.content)) // 4
                            
                            # Shorten assistant thinking if it's long
                            if msg.role == "assistant" and hasattr(msg, 'content') and msg.content and len(msg.content) > 150:
                                if not (hasattr(msg, 'tool_calls') and msg.tool_calls):
                                    # Only shorten if no tool_calls
                                    original_len = len(msg.content)
                                    msg.content = msg.content[:150] + "...[condensed]"
                                    tokens_saved += (original_len - len(msg.content)) // 4
                        
                        # Remove completed step from tracking
                        del self._step_start_message_index[step_idx]
                        
                        if tokens_saved > 0:
                            logger.info(
                                f"🗜️  Condensed step {step_idx}: Shortened content (saved ~{tokens_saved} tokens)"
                            )
        except Exception as e:
            logger.debug(f"Error condensing steps: {e}")
            pass

    async def _save_step_to_firestore_immediately(
        self, tool_calls_data, tool_results_data, screenshots
    ):
        """Save step to Firestore immediately after tool execution"""
        try:
            from app.firestore import firestore_client
            from app.webhook import StepExecutionSchema

            if not firestore_client.enabled:
                return

            # Use thinking from current turn (captured in think() phase)
            thinking = self._current_thinking

            # Use cached timestamp if available (to ensure same doc_id for before/after saves)
            # Otherwise generate new one
            if self._current_step_timestamp:
                timestamp = self._current_step_timestamp
            else:
                timestamp = datetime.utcnow().isoformat() + "Z"

            # Create step data
            has_screenshots = bool(screenshots)
            step_data = StepExecutionSchema(
                step_number=self.current_step,
                timestamp=timestamp,
                agent_name=self.name,
                user_id=getattr(self, "user_id", None),
                session_id=getattr(self, "session_id", None),
                tenant_id=getattr(self, "tenant_id", None),
                test_case_id=getattr(self, "test_case_id", None),
                thinking=thinking,
                tool_calls=tool_calls_data,
                tool_results=tool_results_data,
                screenshots=screenshots,
                screenshot_urls=[],
                status=(
                    "pending_upload"
                    if has_screenshots
                    else ("success" if tool_results_data else "thinking")
                ),
            )

            # Save to Firestore immediately
            logger.debug(f"💾 Saving step {self.current_step} to Firestore...")
            save_start = __import__('time').time()
            await firestore_client.save_step(step_data, [])
            save_elapsed = __import__('time').time() - save_start
            logger.info(
                f"⏱️  Firestore save_step took: {save_elapsed:.2f}s"
            )

        except Exception as e:
            logger.debug(f"Error saving to Firestore: {e}")
            pass

    async def _send_webhook_data(self, tool_calls_data, tool_results_data, screenshots):
        """Update session metadata (step already saved immediately)"""
        try:
            from app.firestore import firestore_client
            
            if not firestore_client.enabled:
                return
                
            # Use thinking from current turn (same as what was saved to step)
            thinking = self._current_thinking

            # Update session metadata (skip for sub-agents - they share parent's session)
            is_sub_agent = "SubAgent" in self.name
            
            if not is_sub_agent:
                # Update session with last output (prefer thinking over tool output)
                last_output = None
                if thinking:
                    # Use thinking if available
                    last_output = thinking
                elif tool_results_data and tool_results_data[0].get("output"):
                    # Otherwise use tool output
                    last_output = tool_results_data[0]["output"]

                if last_output:
                    session_id = getattr(self, "session_id", None)
                    if session_id:
                        await firestore_client.update_session_last_output(
                            session_id, self.current_step, last_output
                        )

                # Update session costs
                session_id = getattr(self, "session_id", None)
                if session_id and hasattr(self.llm, "total_input_tokens"):
                    total_tokens = (
                        self.llm.total_input_tokens + self.llm.total_completion_tokens
                    )
                    total_cost = getattr(self.llm, "total_cost", 0.0)
                    await firestore_client.update_session_costs(
                        session_id, total_tokens, total_cost
                    )

        except Exception as e:
            # Silently fail - webhook/firestore errors shouldn't break agent
            pass

    async def execute_tool(self, command: ToolCall) -> str:
        """Execute a single tool call with robust error handling"""
        if not command or not command.function or not command.function.name:
            return "Error: Invalid command format"

        name = command.function.name
        if name not in self.available_tools.tool_map:
            return f"Error: Unknown tool '{name}'"

        try:
            # Parse arguments
            args = json.loads(command.function.arguments or "{}")

            # Execute the tool
            result = await self.available_tools.execute(name=name, tool_input=args)

            # Handle special tools
            await self._handle_special_tool(name=name, result=result)

            # Check if result is a ToolResult with base64_image
            if hasattr(result, "base64_image") and result.base64_image:
                # Store the base64_image for later use in tool_message
                self._current_base64_image = result.base64_image

            # Return result directly (clean output for Firestore)
            observation = (
                str(result) if result else f"Tool '{name}' completed with no output"
            )

            return observation
        except json.JSONDecodeError as e:
            error_msg = f"Error parsing arguments for {name}: Invalid JSON format - {str(e)}"
            logger.error(
                f"📝 Oops! The arguments for '{name}' don't make sense - invalid JSON"
            )
            logger.error(f"Raw arguments (full): {command.function.arguments if command.function.arguments else 'None'}")
            logger.error(f"JSON decode error: {str(e)}")
            return f"Error: {error_msg}"
        except Exception as e:
            error_msg = f"⚠️ Tool '{name}' encountered a problem: {str(e)}"
            logger.exception(error_msg)
            logger.error(f"Tool args (full): {command.function.arguments if command.function.arguments else 'None'}")
            return f"Error: {error_msg}"

    async def _handle_special_tool(self, name: str, result: Any, **kwargs):
        """Handle special tool execution and state changes"""
        if not self._is_special_tool(name):
            return

        if self._should_finish_execution(name=name, result=result, **kwargs):
            # Agent is terminating - mark any in-progress steps as blocked
            logger.info(f"🏁 Special tool '{name}' has completed the task!")
            logger.info(f"🔄 About to mark incomplete steps as blocked...")
            try:
                await self._mark_incomplete_steps_as_blocked()
                logger.info(f"✅ Finished marking incomplete steps as blocked")
            except Exception as e:
                logger.error(f"❌ Exception in _mark_incomplete_steps_as_blocked: {e}")
                import traceback
                traceback.print_exc()
            
            # Save all proven steps to Firestore at session end
            logger.info(f"💾 Saving all proven steps to Firestore...")
            try:
                await self._save_all_proven_steps()
                logger.info(f"✅ Proven steps saved successfully")
            except Exception as e:
                logger.error(f"❌ Exception saving proven steps: {e}")
            
            self.state = AgentState.FINISHED

    @staticmethod
    def _should_finish_execution(**kwargs) -> bool:
        """Determine if tool execution should finish the agent"""
        return True

    def _is_special_tool(self, name: str) -> bool:
        """Check if tool name is in special tools list"""
        return name.lower() in [n.lower() for n in self.special_tool_names]

    async def _mark_incomplete_steps_as_blocked(self):
        """Mark any in-progress plan steps as blocked before terminating"""
        try:
            logger.info("🔍 Checking for in-progress steps to mark as blocked...")
            
            # Get the planning tool
            planning_tool = self.available_tools.get_tool("planning")
            if not planning_tool:
                logger.warning("⚠️  Planning tool not found - cannot mark steps as blocked")
                return
            
            logger.debug(f"Planning tool found: {planning_tool}")
            
            # Check if there are any in-progress steps
            if not hasattr(planning_tool, 'plans'):
                logger.warning("⚠️  Planning tool has no 'plans' attribute")
                return
                
            if not hasattr(planning_tool, '_current_plan_id'):
                logger.warning("⚠️  Planning tool has no '_current_plan_id' attribute")
                return
            
            current_plan_id = planning_tool._current_plan_id
            logger.info(f"Current plan ID: {current_plan_id}")
            
            if not current_plan_id:
                logger.info("No active plan - nothing to mark as blocked")
                return
                
            if current_plan_id not in planning_tool.plans:
                logger.warning(f"⚠️  Plan '{current_plan_id}' not found in plans")
                return
            
            plan = planning_tool.plans[current_plan_id]
            steps = plan.get('steps', [])
            step_statuses = plan.get('step_statuses', [])
            logger.info(f"Plan has {len(steps)} steps total")
            
            # Find and mark all in-progress steps as blocked
            blocked_count = 0
            for i in range(len(steps)):
                step_status = step_statuses[i] if i < len(step_statuses) else 'not_started'
                logger.debug(f"Step {i}: {steps[i][:50]}... status={step_status}")
                
                if step_status == 'in_progress':
                    logger.info(f"📝 Marking step {i} as 'blocked' due to termination")
                    # Mark as blocked with reason
                    result = await planning_tool.execute(
                        command='mark_step',
                        plan_id=current_plan_id,
                        step_index=i,
                        step_status='blocked',
                        step_notes='Marked as blocked due to agent termination'
                    )
                    logger.info(f"✅ Step {i} marked as blocked: {result[:100]}")
                    blocked_count += 1
            
            if blocked_count == 0:
                logger.info("✅ No in-progress steps found - all steps properly completed or not started")
            else:
                logger.info(f"✅ Marked {blocked_count} step(s) as blocked")
                
        except Exception as e:
            logger.error(f"❌ Error marking incomplete steps as blocked: {e}")
            import traceback
            traceback.print_exc()

    async def cleanup(self):
        """Clean up resources used by the agent's tools."""
        logger.info(f"🧹 Cleaning up resources for agent '{self.name}'...")
        for tool_name, tool_instance in self.available_tools.tool_map.items():
            if hasattr(tool_instance, "cleanup") and asyncio.iscoroutinefunction(
                tool_instance.cleanup
            ):
                try:
                    logger.debug(f"🧼 Cleaning up tool: {tool_name}")
                    await tool_instance.cleanup()
                except Exception as e:
                    logger.error(
                        f"🚨 Error cleaning up tool '{tool_name}': {e}", exc_info=True
                    )
        logger.info(f"✨ Cleanup complete for agent '{self.name}'.")

    async def run(self, request: Optional[str] = None, skip_cleanup: bool = False) -> str:
        """Run the agent with optional cleanup
        
        Args:
            request: Optional initial user request
            skip_cleanup: If True, skip cleanup (for sub-agents sharing resources)
        """
        try:
            return await super().run(request)
        finally:
            if not skip_cleanup:
                await self.cleanup()
            else:
                logger.debug("Skipping cleanup (skip_cleanup=True)")
