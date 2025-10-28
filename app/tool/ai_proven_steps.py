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


