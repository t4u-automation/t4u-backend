"""AI Proven Steps Tool - Save execution history for AI analysis"""

import json
import re

from app.tool.base import BaseTool, ToolResult
from app.utils.logger import logger

_AI_PROVEN_STEPS_DESCRIPTION = """\
Save the complete execution history (all steps, thinking, actions, results) for AI analysis.

IMPORTANT: Call this BEFORE terminate() if you have a test_case_id.

This saves all your exploration (successful and failed attempts) to the test_case.
A Cloud Function will then use AI to extract only the optimal path for replay.

Use this when:
- Task is successfully completed
- You have tried multiple approaches (some worked, some didn't)
- You want to save the successful path for future replay

Provide a summary of what was accomplished.
"""


class AIProvenSteps(BaseTool):
    name: str = "ai_proven_steps"
    description: str = _AI_PROVEN_STEPS_DESCRIPTION
    parameters: dict = {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Brief summary of what was accomplished in this session",
            }
        },
        "required": ["summary"],
    }

    # This will be set by the agent when it creates the tool
    _agent_ref = None
    
    def set_agent(self, agent):
        """Set reference to agent for accessing execution_history"""
        self._agent_ref = agent
    
    async def execute(self, summary: str, **kwargs) -> ToolResult:
        """
        Analyze execution history with LLM and extract proven steps
        
        Args:
            summary: Brief summary of session accomplishment
        """
        try:
            from app.firestore import firestore_client
            
            if not self._agent_ref:
                return self.fail_response("Agent reference not set")
            
            # Get execution history from agent
            execution_history = getattr(self._agent_ref, '_execution_history', [])
            
            if not execution_history:
                return self.fail_response("No execution history to save")
            
            # Get test_case_id and session_id from agent
            test_case_id = getattr(self._agent_ref, 'test_case_id', None)
            session_id = getattr(self._agent_ref, 'session_id', None)
            
            if not test_case_id:
                return self.fail_response("No test_case_id - cannot save to test_case")
            
            print(f"\n{'='*70}")
            print(f"🤖 ANALYZING EXECUTION HISTORY WITH AI")
            print(f"{'='*70}")
            print(f"Total steps to analyze: {len(execution_history)}")
            
            # Use agent's LLM to analyze execution history
            llm = getattr(self._agent_ref, 'llm', None)
            if not llm:
                return self.fail_response("No LLM available for analysis")
            
            # Create prompt for LLM to analyze steps
            analysis_prompt = self._create_analysis_prompt(execution_history, summary)
            
            # Call LLM to analyze
            from app.schema import Message
            response = await llm.ask(
                messages=[Message.user_message(analysis_prompt)],
                system_msgs=[Message.system_message(
                    "You are an expert at analyzing test automation execution logs. "
                    "Extract only the essential steps that led to success, removing failed attempts and unnecessary exploration."
                )]
            )
            
            # llm.ask() returns a string directly
            llm_response_text = response if isinstance(response, str) else str(response)
            
            # Parse LLM response to get proven_steps
            proven_steps = self._parse_proven_steps(llm_response_text)
            
            print(f"✅ AI extracted {len(proven_steps)} proven steps from {len(execution_history)} total steps")
            
            # Save to Firestore test_cases collection
            await firestore_client.save_execution_history_to_test_case(
                test_case_id=test_case_id,
                session_id=session_id,
                execution_history=execution_history,
                summary=summary
            )
            
            # Also save the proven_steps to test_case
            doc_ref = firestore_client.db.collection("test_cases").document(test_case_id)
            doc_ref.update({
                "proven_steps": proven_steps,
                "status": "analyzed",
                "proven_steps_count": len(proven_steps)
            })
            
            print(f"✅ Saved to test_case {test_case_id}")
            print(f"{'='*70}\n")
            
            # Execute AFTER shared test cases if configured
            await self._execute_after_shared_test_cases(test_case_id)
            
            return self.success_response(
                f"✅ AI analyzed {len(execution_history)} steps\n"
                f"✅ Extracted {len(proven_steps)} proven steps\n"
                f"✅ Saved to test_case for replay"
            )
            
        except Exception as e:
            logger.error(f"Error in ai_proven_steps: {e}")
            import traceback
            traceback.print_exc()
            return self.fail_response(f"Failed to analyze execution history: {e}")
    
    def _create_analysis_prompt(self, execution_history: list, summary: str) -> str:
        """Create prompt for LLM to analyze execution history"""
        
        # Format execution history for LLM with FULL context
        history_text = f"Session Summary: {summary}\n\nExecution History ({len(execution_history)} steps):\n\n"
        
        for i, step in enumerate(execution_history, 1):
            history_text += f"Step {step['step_number']} ({step['agent']}):\n"
            history_text += f"  Thinking: {step['thinking']}\n"  # Full thinking
            history_text += f"  Action: {step['tool_call']['tool_name']}"
            
            args = step['tool_call'].get('arguments', {})
            if 'action' in args:
                history_text += f" → {args['action']}"
            
            # Show ALL arguments
            history_text += f"\n  Arguments: {json.dumps(args, indent=2)}\n"
            
            # Show FULL result (critical for seeing exact selectors/values)
            history_text += f"  Result: {'✅ Success' if step['success'] else '❌ Failed'}\n"
            if step['success']:
                # Include full result for successful steps (AI needs this!)
                full_result = step.get('result_full', step.get('result', ''))
                history_text += f"  Output: {full_result}\n"
            else:
                history_text += f"  Error: {step.get('result_full', step.get('result', ''))[:200]}\n"
            history_text += "\n"
        
        prompt = f"""{history_text}

TASK: Analyze the above execution history and extract ONLY the steps that:
1. Were successful (✅)
2. Actually led to progress toward the goal
3. Form a clean, optimal path for replay

REMOVE:
- Failed attempts (❌) - NEVER keep steps that failed!
- Dead ends and retries
- Unnecessary exploration (clicking articles when only asked to validate)
- Extra verification steps after success
- INFO tools used for decision-making: get_elements, get_headings, get_buttons, get_links, get_inputs
- get_by_role used just to check before assertions (assertion does this itself)

🚨 CRITICAL: If an assertion FAILED during exploration, don't keep it!
  Example: assert_count_equals failed (found 2) → get_by_role succeeded (found 5) → Use get_by_role!
  
  BAD: Keep failed assert_count_equals action
  GOOD: Use get_by_role action to find elements
    action: get_by_role('article')
    validation: count_equals to verify count
  
🚨 PREFER LOCATOR-BASED ACTIONS (Stable, No Indices):
  - If agent used get_buttons() → click_element(index), CONVERT to:
    click(by_text="Button Text")
  - If agent used get_inputs() → input_text(index), CONVERT to:
    fill(by_placeholder="Placeholder Text", text="...")
  - Extract exact text/placeholder from exploration results
  - NEVER keep index-based actions if you can extract stable locator

KEEP ACTION tools that modify state, validate, OR wait:
- navigate_to
- click_element  
- input_text
- scroll_down, scroll_up
- wait (if used between actions for timing)
- wait_for_url (if used to wait for navigation)
- wait_for_selector (if used to wait for specific element)
- assert_* (ALL assertions - these are test validations!)
- Any action that was necessary for success

🚨 CRITICAL: ALWAYS KEEP ALL assert_* ACTIONS!
- assert_url_contains
- assert_element_visible
- assert_element_hidden
- assert_text_contains
- assert_count_equals
- assert_has_value
These are test validations and MUST be in proven steps for replay testing!

🚨 ASSERTION PARAMETERS - ENSURE COMPLETENESS:
- All assertions MUST have assertion_description
- assert_count_equals MUST have locator_type if counting semantic elements
  
Examples of fixing incomplete assertions:
- assert_count_equals(search_text="article", expected_count=5)
  → ADD: locator_type="role", assertion_description="Found 5 articles"
- assert_url_contains(expected_text="/dashboard")
  → ADD: assertion_description="On dashboard page"
- assert_count_equals to count semantic elements
  → Replace with: assert_count_equals(search_text="article", expected_count=N, locator_type="role", ...)
  
NEVER leave assertion_description or locator_type empty!

🚨 ALSO KEEP: wait, wait_for_url, wait_for_selector if they were used
These help with timing during replay when pages load slowly.

Return a JSON array with SIMPLE format - NO action wrapper, NO validation field:
```json
[
  {{
    "step_number": 1,
    "tool_name": "e2b_browser",
    "arguments": {{"action": "navigate_to", "url": "https://example.com"}}
  }},
  {{
    "step_number": 2,
    "tool_name": "e2b_browser",
    "arguments": {{"action": "click", "by_text": "Sign In"}}
  }},
  {{{{
    "step_number": 9,
    "action": {{{{
      "tool_name": "e2b_browser",
      "arguments": {{{{"action": "navigate_to", "url": "/news"}}}}
    }}}},
    "validation": {{{{
      "type": "js_equals",
      "script": "document.querySelectorAll('article.news-item[data-published]').length",
      "expected_value": "5",
      "description": "5 published news articles with all components present"
    }}}}
  }}}}
]
```

CRITICAL: Keep EXACT successful actions - don't create separate validations!
- If agent used assert_element_visible and it passed → Keep it
- If agent used click(by_text) and it worked → Keep it
- If agent used fill(by_id) and it worked → Keep it
- Assertions ARE the validations - don't duplicate!

Only return the JSON array, nothing else."""
        
        return prompt
    
    def _parse_proven_steps(self, llm_response: str) -> list:
        """Parse LLM response to extract proven steps array"""
        try:
            
            # Extract JSON from response (might be in code block)
            json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', llm_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find JSON array directly
                json_match = re.search(r'\[.*\]', llm_response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    logger.warning("Could not find JSON in LLM response")
                    return []
            
            proven_steps = json.loads(json_str)
            return proven_steps if isinstance(proven_steps, list) else []
            
        except Exception as e:
            logger.error(f"Failed to parse proven steps from LLM: {e}")
            return []
    
    async def _execute_after_shared_test_cases(self, test_case_id: str):
        """
        Execute AFTER shared test cases after AI Exploration completes.
        
        This runs after proven steps are saved, for cleanup/teardown
        (e.g., logging out, closing modals).
        
        Args:
            test_case_id: The test case ID that just completed
        """
        try:
            from app.utils.shared_test_cases import (
                get_test_case_data,
                resolve_shared_test_cases,
                CircularDependencyError,
                SharedTestCaseNotFoundError
            )
            
            if not self._agent_ref:
                logger.warning("No agent reference - skipping after test cases")
                return
            
            tenant_id = getattr(self._agent_ref, 'tenant_id', None)
            if not tenant_id:
                logger.warning("No tenant_id - skipping after test cases")
                return
            
            logger.info(f"Checking for AFTER shared test cases for test_case_id: {test_case_id}")
            
            # Get test case data
            test_case_data = await get_test_case_data(test_case_id, tenant_id)
            if not test_case_data:
                logger.warning(f"Test case {test_case_id} not found - skipping after test cases")
                return
            
            # Check for shared test cases
            shared_test_cases = test_case_data.get("shared_test_cases", {})
            after_tc_ids = shared_test_cases.get("after", [])
            
            if not after_tc_ids:
                logger.info("No AFTER shared test cases configured")
                return
            
            logger.info(f"Found {len(after_tc_ids)} AFTER shared test cases: {after_tc_ids}")
            
            # Resolve recursively to get all after test cases
            try:
                resolved = await resolve_shared_test_cases(test_case_id, tenant_id)
                all_after_tc_ids = resolved.get("after", [])
                
                if not all_after_tc_ids:
                    logger.info("No AFTER test cases after resolution")
                    return
                
                logger.info(f"Resolved to {len(all_after_tc_ids)} total AFTER test cases: {all_after_tc_ids}")
                
            except CircularDependencyError as e:
                logger.error(f"Circular dependency in shared test cases: {e}")
                return
            except SharedTestCaseNotFoundError as e:
                logger.error(f"Shared test case not found: {e}")
                return
            
            # Execute each after test case
            logger.info("\n" + "="*70)
            logger.info(f"🔷 EXECUTING AFTER TEST CASES ({len(all_after_tc_ids)})")
            logger.info("="*70)
            
            for idx, after_tc_id in enumerate(all_after_tc_ids):
                logger.info(f"\n▶ [{idx + 1}/{len(all_after_tc_ids)}] Executing AFTER: {after_tc_id}")
                
                # Get after test case data
                after_tc_data = await get_test_case_data(after_tc_id, tenant_id)
                if not after_tc_data:
                    logger.error(f"After test case not found: {after_tc_id}")
                    continue
                
                # Send after test case START event to Firestore
                try:
                    from datetime import datetime
                    from app.firestore import firestore_client
                    from app.webhook import StepExecutionSchema
                    
                    session_id = getattr(self._agent_ref, "session_id", None)
                    user_id = getattr(self._agent_ref, "user_id", None)
                    
                    start_event = StepExecutionSchema(
                        step_number=0,
                        timestamp=datetime.utcnow().isoformat() + "Z",
                        agent_name=getattr(self._agent_ref, "name", "E2BTestOpsAI"),
                        session_id=session_id,
                        user_id=user_id,
                        tenant_id=tenant_id,
                        test_case_id=test_case_id,
                        event_type="after_test_case_start",
                        status="running",
                        thinking=f"Executing after test case {idx + 1}/{len(all_after_tc_ids)}: {after_tc_data.get('summary', after_tc_id)}"
                    )
                    
                    if firestore_client.enabled:
                        await firestore_client.save_step(start_event, [])
                except Exception as e:
                    logger.debug(f"Failed to send after_test_case_start event: {e}")
                
                proven_steps = after_tc_data.get("proven_steps", [])
                if not proven_steps:
                    logger.warning(f"No proven steps in after test case: {after_tc_id}")
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
                    
                    # Get tool from agent
                    tool = self._agent_ref.available_tools.get_tool(tool_name)
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
                            # Continue on error in after test cases (cleanup should try to complete)
                        else:
                            logger.info(f"    ✅ Success")
                            passed += 1
                    except Exception as e:
                        logger.error(f"    ❌ Exception: {str(e)}")
                        failed += 1
                        # Continue on error (cleanup should try to complete)
                
                # Send after test case END event to Firestore
                final_status = "failed" if failed > 0 else "success"
                try:
                    from datetime import datetime
                    from app.firestore import firestore_client
                    from app.webhook import StepExecutionSchema
                    
                    session_id = getattr(self._agent_ref, "session_id", None)
                    user_id = getattr(self._agent_ref, "user_id", None)
                    
                    status_emoji = "✅" if final_status == "success" else "❌"
                    end_event = StepExecutionSchema(
                        step_number=0,
                        timestamp=datetime.utcnow().isoformat() + "Z",
                        agent_name=getattr(self._agent_ref, "name", "E2BTestOpsAI"),
                        session_id=session_id,
                        user_id=user_id,
                        tenant_id=tenant_id,
                        test_case_id=test_case_id,
                        event_type="after_test_case_end",
                        status=final_status,
                        thinking=f"{status_emoji} After test case {idx + 1}/{len(all_after_tc_ids)} completed: {after_tc_data.get('summary', after_tc_id)} ({passed}/{len(proven_steps)} steps passed)"
                    )
                    
                    if firestore_client.enabled:
                        await firestore_client.save_step(end_event, [])
                except Exception as e:
                    logger.debug(f"Failed to send after_test_case_end event: {e}")
                
                if failed > 0:
                    logger.warning(f"\n⚠️  AFTER test case '{after_tc_id}' had errors ({passed} passed, {failed} failed)")
                else:
                    logger.info(f"\n✅ AFTER test case '{after_tc_id}' completed successfully ({passed} steps)")
            
            logger.info("\n" + "="*70)
            logger.info("✅ AFTER TEST CASES COMPLETED")
            logger.info("="*70 + "\n")
            
        except Exception as e:
            logger.error(f"Error executing after shared test cases: {e}")
            import traceback
            traceback.print_exc()


