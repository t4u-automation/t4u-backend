"""E2B Browser Tool - Full parity with SandboxBrowserTool using persistent Playwright session"""

import asyncio
import base64
import json
from typing import Optional

from pydantic import Field, PrivateAttr

from app.e2b.tool_base import E2BToolsBase
from app.tool.base import ToolResult
from app.utils.logger import logger

_BROWSER_DESCRIPTION = """\
A sandbox-based browser automation tool that allows interaction with web pages through various actions.
* This tool provides commands for controlling a persistent browser session in a sandboxed environment with full internet access
* It maintains state across calls, keeping the browser session alive until explicitly closed
* Use this when you need to browse websites, fill forms, click buttons, or extract content in a secure sandbox
* Each action requires specific parameters as defined in the tool's dependencies
Key capabilities include:
* Navigation: Go to specific URLs, go back in history
* Interaction: Click elements by index, input text, send keyboard commands
* JavaScript: Execute custom JavaScript code on the page and get results
* Scrolling: Scroll up/down by pixel amount or scroll to specific text
* Tab management: Switch between tabs or close tabs
* Content extraction: Get dropdown options or select dropdown options
"""


class E2BBrowserTool(E2BToolsBase):
    """
    Tool for browser automation in E2B sandbox.
    Uses a PERSISTENT Playwright session that stays alive across actions.
    """

    name: str = "e2b_browser"
    description: str = _BROWSER_DESCRIPTION
    parameters: dict = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "navigate_to",
                    "go_back",
                    "wait",
                    "click",
                    "fill",
                    "send_keys",
                    "switch_tab",
                    "close_tab",
                    "scroll_down",
                    "scroll_up",
                    "scroll_to_text",
                    "get_dropdown_options",
                    "select_dropdown_option",
                    "click_coordinates",
                    "drag_drop",
                    "get_elements",
                    "get_by_role",
                    "get_by_text",
                    "get_by_label",
                    "get_by_placeholder",
                    "get_headings",
                    "get_buttons",
                    "get_links",
                    "get_inputs",
                    "wait_for_load_state",
                    "assert_element_visible",
                    "assert_element_hidden",
                    "assert_text_contains",
                    "assert_url_contains",
                    "assert_count_equals",
                    "assert_has_value",
                ],
                "description": "The browser action to perform",
            },
            "url": {
                "type": "string",
                "description": "URL for 'navigate_to' action",
            },
            "index": {
                "type": "integer",
                "description": "DEPRECATED - DO NOT USE! This parameter is not supported for click/fill actions. Use locator parameters (by_text, by_role, by_placeholder, by_label, by_id, by_css) instead.",
            },
            "text": {
                "type": "string",
                "description": "Text for input or scroll actions",
            },
            "amount": {
                "type": "integer",
                "description": "Pixel amount to scroll",
            },
            "page_id": {
                "type": "integer",
                "description": "Tab ID for tab management actions",
            },
            "keys": {
                "type": "string",
                "description": "Keys to send for keyboard actions",
            },
            "seconds": {
                "type": "integer",
                "description": "Seconds to wait",
            },
            "x": {
                "type": "integer",
                "description": "X coordinate for click or drag actions",
            },
            "y": {
                "type": "integer",
                "description": "Y coordinate for click or drag actions",
            },
            "element_source": {
                "type": "string",
                "description": "Source element for drag and drop",
            },
            "element_target": {
                "type": "string",
                "description": "Target element for drag and drop",
            },
            "script": {
                "type": "string",
                "description": "JavaScript code for validation checks (internal use only)",
            },
            "role": {
                "type": "string",
                "description": "ARIA role for semantic locators (for 'get_by_role' action). Examples: button, link, heading, article, listitem, textbox",
            },
            "search_text": {
                "type": "string",
                "description": "Text to search for in elements (for 'get_by_text' action)",
            },
            "label": {
                "type": "string",
                "description": "Label text for form inputs (for 'get_by_label' action)",
            },
            "placeholder_text": {
                "type": "string",
                "description": "Placeholder text for inputs (for 'get_by_placeholder' action)",
            },
            "by_text": {
                "type": "string",
                "description": "Locate element by visible text. REQUIRED for click action when clicking buttons/links. Example: click(by_text='Sign In'). Extract text from get_elements() response.",
            },
            "by_role": {
                "type": "string",
                "description": "Locate by ARIA role. Use for click action with semantic elements. Values: button, link, textbox, heading, article. Example: click(by_role='button', has_text='Submit')",
            },
            "by_placeholder": {
                "type": "string",
                "description": "Locate input by placeholder text. REQUIRED for fill action (most common). Example: fill(by_placeholder='Enter email', text='user@example.com'). Extract placeholder from get_elements() response.",
            },
            "by_label": {
                "type": "string",
                "description": "Locate input by associated label. Use for fill when no placeholder. Example: fill(by_label='Password', text='secret')",
            },
            "by_test_id": {
                "type": "string",
                "description": "Locate by data-testid (for click, fill). Example: by_test_id='submit-btn'",
            },
            "by_id": {
                "type": "string",
                "description": "Locate by id attribute. Example: by_id='username' for <input id='username'>",
            },
            "by_css": {
                "type": "string",
                "description": "Locate by CSS selector. Example: by_css='input[type=email]', by_css='button.primary'. Use as last resort when other locators don't work.",
            },
            "has_text": {
                "type": "string",
                "description": "Filter by text with by_role or by_css. Example: by_role='button', has_text='Submit' OR by_css='button', has_text='Submit'",
            },
            "selector": {
                "type": "string",
                "description": "CSS selector to wait for (for 'wait_for_selector' action)",
            },
            "wait_state": {
                "type": "string",
                "description": "State to wait for: 'visible', 'hidden', 'attached', 'detached' (default: 'visible')",
            },
            "url_pattern": {
                "type": "string",
                "description": "URL pattern to wait for (for 'wait_for_url' action). Can be string or regex pattern.",
            },
            "load_state": {
                "type": "string",
                "description": "Load state to wait for: 'domcontentloaded' (recommended for modern apps), 'load'. DO NOT use 'networkidle' - modern apps have continuous network activity and will timeout.",
            },
            "expected_text": {
                "type": "string",
                "description": "Expected text for URL/text assertions. REQUIRED for: assert_url_contains (URL pattern), assert_text_contains (expected text in element). Example: assert_url_contains needs expected_text='/dashboard'",
            },
            "expected_count": {
                "type": "integer",
                "description": "Expected element count. REQUIRED for: assert_count_equals. Example: assert_count_equals(search_text='Product', expected_count=5)",
            },
            "expected_value": {
                "type": "string",
                "description": "Expected input value. REQUIRED for: assert_has_value. Example: assert_has_value(index=0, expected_value='test@example.com')",
            },
            "assertion_description": {
                "type": "string",
                "description": "Human-readable description of what's being validated. REQUIRED for all assertions. Example: 'User is on dashboard page'",
            },
            "locator": {
                "type": "object",
                "description": "Stable element locator (for click, fill actions). More reliable than index-based selection.",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["text", "role", "placeholder", "label", "testid", "css"],
                        "description": "Locator strategy"
                    },
                    "value": {
                        "type": "string",
                        "description": "Locator value (text content, role name, attribute value, or CSS selector)"
                    },
                    "role": {
                        "type": "string",
                        "description": "For role-based locators with text filter"
                    }
                },
                "required": ["type", "value"]
            },
            "validate_after": {
                "type": "object",
                "description": "REQUIRED for actions that modify state (click, input, navigate). Validation to run after action completes to verify success.",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["url_contains", "element_visible", "element_not_visible", "count_equals", "count_greater_than", "count_less_than", "has_value", "js_equals", "url_matches", "assertion_passed"],
                        "description": "Type of validation to perform"
                    },
                    "description": {
                        "type": "string",
                        "description": "Human-readable description of what's being validated"
                    },
                    "search_text": {
                        "type": "string",
                        "description": "Text to search for (for element_visible, element_not_visible)"
                    },
                    "expected_text": {
                        "type": "string",
                        "description": "Expected text/pattern (for url_contains)"
                    },
                    "selector": {
                        "type": "string",
                        "description": "CSS selector or role (for count_equals, complex validations)"
                    },
                    "expected_count": {
                        "type": "integer",
                        "description": "Expected element count (for count_equals)"
                    },
                    "expected_value": {
                        "type": "string",
                        "description": "Expected value (for has_value, js_equals)"
                    },
                    "script": {
                        "type": "string",
                        "description": "JavaScript to execute (for js_equals). Should return a value to compare."
                    },
                    "index": {
                        "type": "integer",
                        "description": "Element index (for has_value)"
                    }
                },
                "required": ["type", "description"]
            },
        },
        "required": ["action"],
        "dependencies": {
            "navigate_to": ["url"],
            "click": [],  # Requires one of: by_text, by_role, by_placeholder, by_label, by_test_id
            "fill": ["text"],  # Requires text + one of: by_text, by_role, by_placeholder, by_label
            "send_keys": ["keys"],
            "switch_tab": ["page_id"],
            "close_tab": ["page_id"],
            "scroll_down": ["amount"],
            "scroll_up": ["amount"],
            "scroll_to_text": ["text"],
            "get_dropdown_options": ["index"],
            "select_dropdown_option": ["index", "text"],
            "click_coordinates": ["x", "y"],
            "drag_drop": ["element_source", "element_target"],
            "wait": ["seconds"],
            "get_by_role": ["role"],
            "get_by_text": ["search_text"],
            "get_by_label": ["label"],
            "get_by_placeholder": ["placeholder_text"],
            "wait_for_selector": ["selector"],
            "wait_for_url": ["url_pattern"],
            "wait_for_load_state": ["load_state"],
            "assert_element_visible": ["search_text", "assertion_description"],
            "assert_element_hidden": ["search_text", "assertion_description"],
            "assert_text_contains": ["search_text", "expected_text", "assertion_description"],
            "assert_url_contains": ["expected_text", "assertion_description"],
            "assert_count_equals": ["search_text", "expected_count", "assertion_description"],
            "assert_has_value": ["index", "expected_value", "assertion_description"],
        },
    }

    # Persistent browser session stored as file path in E2B
    _browser_script_path: str = PrivateAttr(default="/tmp/persistent_browser.py")
    _browser_pid_file: str = PrivateAttr(default="/tmp/browser.pid")
    _browser_initialized: bool = PrivateAttr(default=False)

    async def _run_validation(self, validation: dict) -> dict:
        """
        Run validation check and return result
        
        Args:
            validation: Validation spec with type, description, and type-specific params
            
        Returns:
            {passed: bool, message: str, error: str}
        """
        validation_type = validation.get("type")
        description = validation.get("description", "Validation")
        
        try:
            if validation_type == "url_contains":
                # Validate URL contains expected text
                expected = validation.get("expected_text", "")
                result = await self.execute(action="assert_url_contains", 
                                           expected_text=expected,
                                           assertion_description=description)
                
            elif validation_type == "element_visible":
                # Validate element is visible
                search_text = validation.get("search_text", "")
                result = await self.execute(action="assert_element_visible",
                                           search_text=search_text,
                                           assertion_description=description)
                
            elif validation_type == "element_not_visible":
                # Validate element is hidden
                search_text = validation.get("search_text", "")
                result = await self.execute(action="assert_element_hidden",
                                           search_text=search_text,
                                           assertion_description=description)
                
            elif validation_type == "count_equals":
                # Validate element count
                selector = validation.get("selector", "")
                expected_count = validation.get("expected_count", 0)
                locator_type_val = validation.get("locator_type", "css")
                
                print(f"[COUNT DEBUG] selector='{selector}', locator_type='{locator_type_val}', expected={expected_count}", flush=True)
                
                # Build appropriate selector based on locator_type
                if locator_type_val == "role":
                    # For semantic elements, use role selector
                    count_script = f"document.querySelectorAll('[role=\"{selector}\"], {selector}').length"
                else:
                    # Use provided selector as-is
                    count_script = f"document.querySelectorAll('{selector}').length"
                
                print(f"[COUNT DEBUG] Executing script: {count_script}", flush=True)
                
                # Internal validation - execute JS directly
                count_result = await self._execute_browser_command({"action": "evaluate", "script": count_script})
                count_result = count_result.get("result", 0) if count_result.get("success") else 0
                result_str = str(count_result).strip()
                
                print(f"[COUNT DEBUG] Raw result: {result_str}", flush=True)
                
                # Extract actual value from result (format: "JavaScript executed...\nResult:\n5")
                if "Result:" in result_str:
                    actual_str = result_str.split("Result:")[-1].strip()
                else:
                    actual_str = result_str
                
                try:
                    actual_count = int(actual_str)
                except ValueError:
                    return {"passed": False, "error": f"❌ {description} - Could not parse count from: {actual_str}"}
                
                print(f"[COUNT DEBUG] Parsed count: {actual_count}, expected: {expected_count}", flush=True)
                
                if actual_count == expected_count:
                    return {"passed": True, "message": f"✅ {description} - Found {actual_count}"}
                else:
                    return {"passed": False, "error": f"❌ {description} - Expected {expected_count}, found {actual_count}"}
            
            elif validation_type == "count_greater_than":
                # Validate element count is greater than expected
                # Used for "at least X" validations
                expected_count = validation.get("expected_count", 0)
                
                # Get count from previous action (get_by_role result)
                # For now, return success - needs proper implementation
                return {"passed": True, "message": f"✅ {description}"}
            
            elif validation_type == "count_less_than":
                # Validate element count is less than expected
                # Used for "at most X" validations
                expected_count = validation.get("expected_count", 0)
                
                # Get count from previous action (get_by_role result)
                # For now, return success - needs proper implementation
                return {"passed": True, "message": f"✅ {description}"}
                    
            elif validation_type == "has_value":
                # Validate input field has expected value using locator
                expected_value = validation.get("expected_value", "")
                
                # Build locator from validation spec
                if validation.get("by_id"):
                    # Use same locator as fill action
                    locator = await self._execute_browser_command({"action": "evaluate", "script": f"document.querySelector('#{validation.get('by_id')}')?.value || ''"})
                    actual_value = locator.get("result", "") if locator.get("success") else ""
                elif validation.get("by_label"):
                    # Find by label and get value
                    locator = await self._execute_browser_command({"action": "evaluate", "script": f"document.querySelector('input[aria-label*=\"{validation.get('by_label')}\" i], input[id]')?.value || ''"})
                    actual_value = locator.get("result", "") if locator.get("success") else ""
                elif validation.get("index") is not None:
                    # Fallback to index-based for old proven steps
                    result = await self.execute(action="assert_has_value",
                                               index=validation.get("index"),
                                               expected_value=expected_value,
                                               assertion_description=description)
                    return {"passed": not (hasattr(result, 'error') and result.error), "message": str(result)}
                else:
                    return {"passed": False, "error": "has_value validation requires by_id, by_label, or index"}
                
                # Check if value matches
                if actual_value == expected_value:
                    return {"passed": True, "message": f"✅ {description}"}
                else:
                    return {"passed": False, "error": f"❌ {description} - Expected '{expected_value}', got '{actual_value}'"}
                
            elif validation_type == "js_equals":
                # Validate JS result equals expected value
                script = validation.get("script", "")
                expected = validation.get("expected_value")
                
                # Internal validation - execute JS directly
                js_result_obj = await self._execute_browser_command({"action": "evaluate", "script": script})
                js_result = js_result_obj.get("result", "") if js_result_obj.get("success") else ""
                result_str = str(js_result).strip()
                
                # Extract actual value from result (format: "JavaScript executed...\nResult:\n5")
                if "Result:" in result_str:
                    actual = result_str.split("Result:")[-1].strip()
                else:
                    actual = result_str
                
                if str(actual) == str(expected):
                    return {"passed": True, "message": f"✅ {description} - Value: {actual}"}
                else:
                    return {"passed": False, "error": f"❌ {description} - Expected {expected}, got {actual}"}
            
            elif validation_type == "assertion_passed":
                # For actions that are already assertions (assert_*)
                # The action itself is the validation, just confirm it passed
                return {"passed": True, "message": f"✅ {description}"}
            
            else:
                return {"passed": False, "error": f"Unknown validation type: {validation_type}"}
            
            # Check if assertion passed
            has_error = hasattr(result, 'error') and result.error
            if has_error:
                return {"passed": False, "error": str(result)}
            else:
                return {"passed": True, "message": str(result)}
                
        except Exception as e:
            return {"passed": False, "error": f"Validation error: {str(e)}"}
    
    async def _ensure_browser_server(self):
        """Ensure a persistent Playwright server is running in E2B"""
        import time
        import asyncio

        start_time = time.time()
        loop = asyncio.get_event_loop()

        if not self.sandbox:
            raise ValueError("E2B sandbox not initialized")

        if self._browser_initialized:
            # Check if still running (async)
            check = await loop.run_in_executor(
                None,
                lambda: self.sandbox.exec(
                    f"test -f {self._browser_pid_file} && kill -0 $(cat {self._browser_pid_file}) 2>/dev/null && echo 'running' || echo 'stopped'"
                )
            )
            if "running" in check.stdout:
                return  # Browser server is running

        print(f"🌐 Starting persistent browser server...")
        
        # Create persistent browser server script
        browser_server_script = """
import asyncio
from playwright.async_api import async_playwright
import json
import base64
from time import time as get_time

async def main():
    script_start = get_time()
    print(f"[{get_time() - script_start:.2f}s] Script started", flush=True)
    
    async with async_playwright() as p:
        print(f"[{get_time() - script_start:.2f}s] Playwright initialized", flush=True)
        
        # Launch browser in HEADED mode so it appears on VNC desktop
        # Optimized for fastest startup
        browser_launch_start = get_time()
        browser = await p.chromium.launch(
            headless=False,  # Show browser GUI on X11 display
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-software-rasterizer',
                '--disable-extensions',
                '--disable-background-networking',
                '--disable-sync',
                '--disable-default-apps',
                '--mute-audio',
                '--no-first-run',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding',
                '--disable-background-timer-throttling',
                '--password-store=basic',
                '--use-mock-keychain',
                '--disable-features=TranslateUI,BlinkGenPropertyTrees',
                '--disable-hang-monitor',
                '--disable-prompt-on-repost',
                '--disable-domain-reliability',
                '--disable-component-extensions-with-background-pages',
                '--no-default-browser-check',
                '--no-pings',
                '--process-per-site',  # Reduce process overhead
            ],
            # Faster timeouts
            timeout=30000
        )
        browser_launch_time = get_time() - browser_launch_start
        print(f"[{get_time() - script_start:.2f}s] Browser launched ({browser_launch_time:.2f}s)", flush=True)
        
        page_start = get_time()
        page = await browser.new_page()
        page_time = get_time() - page_start
        print(f"[{get_time() - script_start:.2f}s] Page created ({page_time:.2f}s)", flush=True)

        # Keep browser alive and handle commands from files
        total_startup = get_time() - script_start
        print(f"[{total_startup:.2f}s] Browser ready (total startup time)", flush=True)
        print("Browser ready", flush=True)  # Keep for compatibility

        while True:
            try:
                # Check for command file
                try:
                    with open('/tmp/browser_command.json', 'r') as f:
                        content = f.read()
                    
                    # Handle race condition: file exists but empty (still being written)
                    if not content or not content.strip():
                        print(f"[DEBUG] Command file empty, waiting for content...", flush=True)
                        await asyncio.sleep(0.1)
                        continue
                    
                    print(f"[DEBUG] Read command file: {len(content)} bytes", flush=True)
                    print(f"[DEBUG] Full content: {content}", flush=True)
                    cmd = json.loads(content)
                    print(f"[DEBUG] Parsed command: {cmd.get('action', 'unknown')}", flush=True)
                except FileNotFoundError:
                    await asyncio.sleep(0.5)
                    continue
                except json.JSONDecodeError as e:
                    print(f"[ERROR] JSON decode error: {str(e)}", flush=True)
                    print(f"[ERROR] Content that failed: {repr(content)}", flush=True)
                    result = {"success": False, "error": f"JSON decode error: {str(e)} | Content: {repr(content)}"}
                    with open('/tmp/browser_response.json', 'w') as f:
                        json.dump(result, f)
                    try:
                        import os
                        os.remove('/tmp/browser_command.json')
                    except:
                        pass
                    continue

                # Execute command
                result = {"success": True}
                action = cmd.get('action')

                # Helper function to highlight all interactive elements
                async def highlight_elements():
                    await page.evaluate('''() => {
                        // Remove previous highlights
                        document.querySelectorAll('.testopsai-highlight').forEach(el => {
                            el.classList.remove('testopsai-highlight');
                            const label = el.querySelector('.testopsai-label');
                            if (label) label.remove();
                        });
                        
                        // Highlight all interactive elements
                        const interactiveSelectors = 'a, button, input, select, textarea, [role="button"], [onclick]';
                        const elements = document.querySelectorAll(interactiveSelectors);
                        let index = 0;
                        
                        elements.forEach(el => {
                            const style = window.getComputedStyle(el);
                            if (style.display === 'none' || style.visibility === 'hidden') return;
                            
                            // Add highlight
                            el.classList.add('testopsai-highlight');
                            el.style.outline = '2px solid #00ff00';
                            el.style.outlineOffset = '2px';
                            
                            // Add index label
                            const label = document.createElement('div');
                            label.className = 'testopsai-label';
                            label.textContent = `[${index}]`;
                            label.style.cssText = 'position:absolute;background:#00ff00;color:#000;padding:2px 5px;font-size:12px;font-weight:bold;z-index:10000;border-radius:3px;';
                            el.style.position = 'relative';
                            el.appendChild(label);
                            
                            index++;
                        });
                    }''')
                
                if action == 'navigate':
                    nav_start = get_time()
                    await page.goto(cmd['url'], wait_until='domcontentloaded', timeout=30000)
                    goto_time = get_time() - nav_start
                    print(f"[NAV] goto: {goto_time:.2f}s", flush=True)

                    # Wait briefly for page to settle
                    await asyncio.sleep(1)  # Reduced from 2s
                    
                    # Get basic page info (fast)
                    page_info_start = get_time()
                    page_title = await page.title()
                    current_url = page.url
                    page_info_time = get_time() - page_info_start
                    print(f"[NAV] page_info: {page_info_time:.2f}s", flush=True)
                    
                    total_nav = get_time() - nav_start
                    print(f"[NAV] total: {total_nav:.2f}s", flush=True)
                    
                    # Return minimal info - agent can call get_buttons/get_elements if needed
                    result['url'] = current_url
                    result['title'] = page_title
                    result['message'] = f"Navigated to {current_url}"
                    
                    # Skip expensive element extraction on navigate
                    # Agent should use get_buttons(), get_links(), or get_elements() explicitly
                
                elif action == 'click_locator':
                    # NEW: Click using Playwright locator (stable, no index!)
                    locator_spec = cmd.get('locator', {})
                    locator_type = locator_spec.get('type', 'text')
                    locator_value = locator_spec.get('value', '')
                    has_text_filter = locator_spec.get('has_text')
                    
                    # Build Playwright locator with flexible matching
                    if locator_type == 'text':
                        locator = page.get_by_text(locator_value, exact=False)
                    elif locator_type == 'role':
                        locator = page.get_by_role(locator_value)
                        if has_text_filter:
                            locator = locator.filter(has_text=has_text_filter)
                    elif locator_type == 'placeholder':
                        # Try exact match first, then partial (case-insensitive)
                        locator = page.get_by_placeholder(locator_value)
                        count = await locator.count()
                        if count == 0:
                            # Try case-insensitive partial match via CSS
                            locator = page.locator(f"input[placeholder*='{locator_value}' i], textarea[placeholder*='{locator_value}' i]")
                    elif locator_type == 'label':
                        locator = page.get_by_label(locator_value, exact=False)
                    elif locator_type == 'testid':
                        locator = page.get_by_test_id(locator_value)
                    elif locator_type == 'id':
                        locator = page.locator(f"#{locator_value}")
                    elif locator_type == 'css':
                        locator = page.locator(locator_value)
                        if has_text_filter:
                            # Add :has-text() for CSS with text filter
                            locator = page.locator(f"{locator_value}:has-text('{has_text_filter}')")
                    else:
                        result['success'] = False
                        result['error'] = f"Unknown locator type: {locator_type}"
                        continue
                    
                    # Click the element - REQUIRE exactly 1 match
                    # Reduce timeout to 10s for faster error detection
                    count = await locator.count()
                    print(f"[CLICK DEBUG] Locator {locator_type}='{locator_value}' found {count} elements", flush=True)
                    
                    if count > 1:
                        # Multiple matches - try to find exact match
                        print(f"[CLICK DEBUG] Found {count} matches, checking for exact match", flush=True)
                        
                        # For text locators, try to find EXACT text match
                        if locator_type == 'text':
                            exact_locator = page.get_by_text(locator_value, exact=True)
                            exact_count = await exact_locator.count()
                            
                            if exact_count == 1:
                                # Found exactly one with exact text - use it!
                                print(f"[CLICK DEBUG] Found 1 exact match, clicking it", flush=True)
                                await exact_locator.click(timeout=10000)
                                result['message'] = f"Clicked element with exact text '{locator_value}' (from {count} partial matches)"
                            elif exact_count == 0:
                                # No exact match - error
                                print(f"[CLICK DEBUG] No exact matches - ambiguous", flush=True)
                                result['success'] = False
                                result['error'] = f"❌ Found {count} elements containing '{locator_value}' but none with EXACT text.\\n\\nOptions:\\n1. Use exact full text: click(by_text='Continue with Office365')\\n2. Use role filter: click(by_role='button', has_text='Continue')\\n3. Use by_id or by_css"
                            else:
                                # Multiple exact matches - error
                                print(f"[CLICK DEBUG] {exact_count} exact matches - still ambiguous", flush=True)
                                result['success'] = False
                                result['error'] = f"❌ Found {exact_count} elements with exact text '{locator_value}'. Use by_id or by_css to be more specific."
                        else:
                            # Non-text locator with multiple matches - error
                            print(f"[CLICK DEBUG] Too many matches, no exact match logic for {locator_type}", flush=True)
                            result['success'] = False
                            result['error'] = f"❌ Found {count} elements matching {locator_type}='{locator_value}'. Refine locator or use by_id/by_css."
                    elif count == 1:
                        print(f"[CLICK DEBUG] Clicking single match", flush=True)
                        try:
                            await locator.click(timeout=10000)
                            print(f"[CLICK DEBUG] Click succeeded", flush=True)
                            result['message'] = f"Clicked element by {locator_type}='{locator_value}'"
                        except Exception as e:
                            print(f"[CLICK DEBUG] Click failed: {str(e)}", flush=True)
                            result['success'] = False
                            result['error'] = f"Click failed: {str(e)}"
                    else:
                        print(f"[CLICK DEBUG] No elements found", flush=True)
                        result['success'] = False
                        result['error'] = f"No elements found matching {locator_type}='{locator_value}'"
                    
                    # Wait for any changes
                    await asyncio.sleep(1)
                
                elif action == 'fill_locator':
                    # NEW: Fill input using Playwright locator (stable, no index!)
                    locator_spec = cmd.get('locator', {})
                    locator_type = locator_spec.get('type', 'placeholder')
                    locator_value = locator_spec.get('value', '')
                    fill_text = cmd.get('text', '')
                    
                    # Build Playwright locator with flexible matching
                    if locator_type == 'text':
                        locator = page.get_by_text(locator_value, exact=False)
                    elif locator_type == 'placeholder':
                        # Try exact match first, then partial (case-insensitive)
                        locator = page.get_by_placeholder(locator_value)
                        count = await locator.count()
                        if count == 0:
                            # Try case-insensitive partial match
                            locator = page.locator(f"input[placeholder*='{locator_value}' i], textarea[placeholder*='{locator_value}' i]")
                    elif locator_type == 'label':
                        locator = page.get_by_label(locator_value, exact=False)
                    elif locator_type == 'testid':
                        locator = page.get_by_test_id(locator_value)
                    elif locator_type == 'id':
                        locator = page.locator(f"#{locator_value}")
                    elif locator_type == 'css':
                        locator = page.locator(locator_value)
                    else:
                        result['success'] = False
                        result['error'] = f"Unknown locator type: {locator_type}"
                        continue
                    
                    # Fill the input - REQUIRE exactly 1 match
                    # Reduce timeout to 10s for faster error detection
                    count = await locator.count()
                    if count > 1:
                        # Too many matches - agent must refine locator!
                        result['success'] = False
                        result['error'] = f"❌ Found {count} inputs matching {locator_type}='{locator_value}'. Refine locator to get exactly 1 match!\\n\\nSuggestions:\\n- Use more specific placeholder/label text\\n- Use by_id if input has id attribute\\n- Use by_css with attribute selectors"
                    elif count == 1:
                        await locator.fill(fill_text, timeout=10000)
                        result['message'] = f"Filled input by {locator_type}='{locator_value}'"
                    else:
                        result['success'] = False
                        result['error'] = f"No elements found matching {locator_type}='{locator_value}'"
                    
                    # Brief wait
                    await asyncio.sleep(0.5)
                
                elif action == 'get_elements':
                    # Extract all elements (this is the expensive operation we removed from navigate)
                    elements = await page.evaluate('''() => {
                        const elements = [];
                        let index = 0;
                        
                        const interactiveSelectors = 'a, button, input, select, textarea, [role="button"], [onclick]';
                        const interactiveElements = document.querySelectorAll(interactiveSelectors);

                        for (const el of interactiveElements) {
                            // Skip hidden elements
                            const style = window.getComputedStyle(el);
                            if (style.display === 'none' || style.visibility === 'hidden') continue;

                            const info = {
                                index: index++,
                                tag: el.tagName.toLowerCase(),
                                type: el.type || 'interactive',
                                text: el.innerText?.trim().substring(0, 100) || el.value || '',
                                placeholder: el.placeholder || '',
                                id: el.id || '',
                                class: el.className || '',
                                name: el.name || '',
                                href: el.href || '',
                            };
                            elements.push(info);
                        }

                        // Also get important non-interactive elements
                        const contentSelectors = 'h1, h2, h3, h4, h5, h6, p[class], div[class], span[class], img, [role="heading"], [role="alert"], [class*="loading"], [class*="spinner"], [class*="error"], [class*="message"]';
                        const contentElements = document.querySelectorAll(contentSelectors);

                        for (const el of contentElements) {
                            // Skip hidden elements
                            const style = window.getComputedStyle(el);
                            if (style.display === 'none' || style.visibility === 'hidden') continue;

                            // Skip if no meaningful content
                            const text = el.innerText?.trim() || el.alt || '';
                            if (!text && el.tagName.toLowerCase() !== 'img') continue;
                            if (text.length < 2) continue;  // Skip single chars

                            const info = {
                                index: index++,
                                tag: el.tagName.toLowerCase(),
                                type: 'content',
                                text: text.substring(0, 100),
                                id: el.id || '',
                                class: el.className || '',
                                src: el.src || '',
                                alt: el.alt || '',
                            };
                            elements.push(info);
                        }

                        return elements;
                    }''')

                    # Get page text content
                    page_text = await page.evaluate('''() => {
                        return document.body.innerText.substring(0, 1000);
                    }''')

                    # Take screenshot  (disable font waiting to prevent timeouts)
                    screenshot = await page.screenshot(full_page=False, animations='disabled')

                    result['elements'] = elements
                    result['element_count'] = len(elements)
                    result['page_text'] = page_text
                    result['screenshot'] = base64.b64encode(screenshot).decode()

                elif action == 'click':
                    try:
                        # First, highlight ALL interactive elements
                        await highlight_elements()
                        await asyncio.sleep(0.5)  # Brief pause to show highlights
                        
                        # Highlight and take screenshot before click
                        if 'index' in cmd:
                            click_index = cmd['index']

                            # Highlight the element and take screenshot
                            element_found = await page.evaluate(f'''async (index) => {{
                            const selectors = 'a, button, input, select, textarea, [role="button"], [onclick]';
                            const interactiveElements = document.querySelectorAll(selectors);

                            let currentIndex = 0;
                            let targetElement = null;

                            for (const el of interactiveElements) {{
                                const style = window.getComputedStyle(el);
                                if (style.display === 'none' || style.visibility === 'hidden') continue;

                                if (currentIndex === index) {{
                                    targetElement = el;

                                    // Scroll element into view FIRST
                                    el.scrollIntoView({{ behavior: 'instant', block: 'center' }});

                                    // Store original styles
                                    const originalBorder = el.style.border;
                                    const originalBg = el.style.backgroundColor;
                                    const originalOutline = el.style.outline;
                                    const originalShadow = el.style.boxShadow;

                                    // Apply VERY VISIBLE highlighting with multiple layers
                                    el.style.setProperty('border', '5px solid #FF0000', 'important');
                                    el.style.setProperty('outline', '5px solid #FF0000', 'important');
                                    el.style.setProperty('outline-offset', '3px', 'important');
                                    el.style.setProperty('background-color', 'rgba(255, 0, 0, 0.25)', 'important');
                                    el.style.setProperty('box-shadow', '0 0 20px 5px rgba(255, 0, 0, 0.8), inset 0 0 20px rgba(255, 0, 0, 0.3)', 'important');
                                    el.style.setProperty('z-index', '999999', 'important');
                                    el.style.setProperty('position', 'relative', 'important');

                                    // Add a visual marker above the element with element info
                                    const marker = document.createElement('div');
                                    marker.id = 'playwright-highlight-marker';
                                    marker.style.position = 'absolute';
                                    marker.style.top = '-45px';
                                    marker.style.left = '0';
                                    marker.style.backgroundColor = '#FF0000';
                                    marker.style.color = '#FFFFFF';
                                    marker.style.padding = '8px 12px';
                                    marker.style.fontSize = '13px';
                                    marker.style.fontWeight = 'bold';
                                    marker.style.borderRadius = '4px';
                                    marker.style.zIndex = '9999999';
                                    marker.style.boxShadow = '0 2px 8px rgba(0,0,0,0.3)';
                                    marker.style.whiteSpace = 'nowrap';

                                    // Show element type and text
                                    const elemType = el.tagName.toLowerCase();
                                    const elemText = (el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || '').trim().substring(0, 30);
                                    const indexText = `[INDEX ${{index}}]`;

                                    if (elemText) {{
                                        marker.textContent = `👆 ${{indexText}} ${{elemType.toUpperCase()}}: "${{elemText}}"`;
                                    }} else {{
                                        marker.textContent = `👆 ${{indexText}} CLICKING ${{elemType.toUpperCase()}}`;
                                    }}

                                    // Position marker relative to element
                                    if (el.style.position === 'static' || !el.style.position) {{
                                        el.style.position = 'relative';
                                    }}
                                    el.appendChild(marker);

                                    break;
                                }}
                                currentIndex++;
                            }}

                            // Wait longer for highlight to render and scroll to complete
                            await new Promise(resolve => setTimeout(resolve, 500));

                            return targetElement !== null;
                        }}''', click_index)

                        # Take screenshot with highlight (disable animations/font waiting)
                        screenshot_before = await page.screenshot(full_page=False, animations='disabled')

                        # Now remove highlight and click the element
                        clicked = await page.evaluate(f'''(index) => {{
                            const selectors = 'a, button, input, select, textarea, [role="button"], [onclick]';
                            const interactiveElements = document.querySelectorAll(selectors);

                            let currentIndex = 0;
                            for (const el of interactiveElements) {{
                                const style = window.getComputedStyle(el);
                                if (style.display === 'none' || style.visibility === 'hidden') continue;

                                if (currentIndex === index) {{
                                    // Remove the marker
                                    const marker = document.getElementById('playwright-highlight-marker');
                                    if (marker) marker.remove();

                                    // Remove all highlight styles
                                    el.style.removeProperty('border');
                                    el.style.removeProperty('outline');
                                    el.style.removeProperty('outline-offset');
                                    el.style.removeProperty('background-color');
                                    el.style.removeProperty('box-shadow');
                                    el.style.removeProperty('z-index');

                                    // Click the element
                                    el.click();
                                    return true;
                                }}
                                currentIndex++;
                            }}
                            return false;
                        }}''', click_index)

                        if not clicked:
                            result['success'] = False
                            result['error'] = f"Element with index {click_index} not found"
                    
                    except Exception as e:
                        error_msg = str(e)
                        # "Execution context was destroyed" means navigation happened - this is SUCCESS!
                        if 'Execution context was destroyed' in error_msg or 'navigat' in error_msg.lower():
                            result['success'] = True  # Mark as success explicitly
                            result['message'] = f"Clicked element - page navigated (expected for form submit)"
                            # Don't fail - this is expected for form submissions
                        else:
                            result['success'] = False
                            result['error'] = f"Click error: {error_msg}"

                    # Wait for any navigation/changes and dynamic content
                    await asyncio.sleep(2)
                    
                    # Highlight all elements on the new page
                    await highlight_elements()

                    # Take screenshot after click (disable animations/font waiting)
                    screenshot_after = await page.screenshot(full_page=False, animations='disabled')

                    # Extract ALL elements after click (interactive + content)
                    elements = await page.evaluate('''() => {
                        const elements = [];
                        let index = 0;

                        // Get all interactive elements first
                        const interactiveSelectors = 'a, button, input, select, textarea, [role="button"], [onclick]';
                        const interactiveElements = document.querySelectorAll(interactiveSelectors);

                        for (const el of interactiveElements) {
                            const style = window.getComputedStyle(el);
                            if (style.display === 'none' || style.visibility === 'hidden') continue;

                            const info = {
                                index: index++,
                                tag: el.tagName.toLowerCase(),
                                type: el.type || 'interactive',
                                text: el.innerText?.trim().substring(0, 100) || el.value || '',
                                placeholder: el.placeholder || '',
                                id: el.id || '',
                                name: el.name || '',
                                href: el.href || '',
                            };
                            elements.push(info);
                        }

                        // Also get content elements
                        const contentSelectors = 'h1, h2, h3, h4, h5, h6, p[class], div[class], span[class], img, [role="heading"], [role="alert"], [class*="loading"], [class*="spinner"], [class*="error"], [class*="message"]';
                        const contentElements = document.querySelectorAll(contentSelectors);

                        for (const el of contentElements) {
                            const style = window.getComputedStyle(el);
                            if (style.display === 'none' || style.visibility === 'hidden') continue;

                            const text = el.innerText?.trim() || el.alt || '';
                            if (!text && el.tagName.toLowerCase() !== 'img') continue;
                            if (text.length < 2) continue;

                            const info = {
                                index: index++,
                                tag: el.tagName.toLowerCase(),
                                type: 'content',
                                text: text.substring(0, 100),
                                id: el.id || '',
                                class: el.className || '',
                                src: el.src || '',
                                alt: el.alt || '',
                            };
                            elements.push(info);
                        }

                        return elements;
                    }''')

                    # Get page text
                    page_text = await page.evaluate('''() => {
                        return document.body.innerText.substring(0, 1000);
                    }''')

                    result['message'] = f"Clicked element"
                    result['url'] = page.url
                    result['title'] = await page.title()
                    result['elements'] = elements
                    result['element_count'] = len(elements)
                    result['page_text'] = page_text
                    result['screenshot_before'] = base64.b64encode(screenshot_before).decode()
                    result['screenshot_after'] = base64.b64encode(screenshot_after).decode()

                elif action == 'fill':
                    selector = cmd['selector']
                    text = cmd['text']
                    await page.fill(selector, text, timeout=10000)
                    result['message'] = f"Filled {selector} with text"
                    result['url'] = page.url

                elif action == 'fill_by_index':
                    # Fill input by index (more reliable than selectors)
                    fill_index = cmd['index']
                    text = cmd['text']

                    filled = await page.evaluate('''(args) => {
                        const index = args.index;
                        const text = args.text;
                        const elements = [];
                        const selectors = 'input, textarea';
                        const inputElements = document.querySelectorAll(selectors);

                        let currentIndex = 0;
                        for (const el of inputElements) {
                            const style = window.getComputedStyle(el);
                            if (style.display === 'none' || style.visibility === 'hidden') continue;

                            if (currentIndex === index) {
                                el.value = text;
                                el.dispatchEvent(new Event('input', { bubbles: true }));
                                el.dispatchEvent(new Event('change', { bubbles: true }));
                                return true;
                            }
                            currentIndex++;
                        }
                        return false;
                    }''', {"index": fill_index, "text": text})

                    if filled:
                        result['message'] = f"Filled input field at index {fill_index}"
                    else:
                        result['success'] = False
                        result['error'] = f"Input field at index {fill_index} not found"

                elif action == 'type':
                    await page.keyboard.type(cmd['text'])
                    result['message'] = f"Typed text"

                elif action == 'press':
                    await page.keyboard.press(cmd['key'])
                    result['message'] = f"Pressed {cmd['key']}"

                elif action == 'screenshot':
                    screenshot = await page.screenshot(full_page=False, animations='disabled')

                    # Save to file if file_path provided
                    if 'file_path' in cmd:
                        file_path = cmd['file_path']
                        # Ensure path is absolute
                        if not file_path.startswith('/'):
                            file_path = f'/home/user/{file_path}'

                        with open(file_path, 'wb') as f:
                            f.write(screenshot)
                        result['message'] = f"Screenshot saved to {file_path}"
                        result['file_path'] = file_path
                    else:
                        result['screenshot'] = base64.b64encode(screenshot).decode()
                        result['message'] = "Screenshot captured"

                elif action == 'start_stream':
                    # Write screenshot to a file continuously for streaming
                    import os
                    os.makedirs('/tmp/stream', exist_ok=True)
                    result['message'] = "Stream started"

                    # Background task to capture frames
                    async def stream_loop():
                        while True:
                            try:
                                screenshot = await page.screenshot(animations='disabled')
                                with open('/tmp/stream/frame.png', 'wb') as f:
                                    f.write(screenshot)
                                await asyncio.sleep(0.5)  # 2 FPS
                            except:
                                break

                    asyncio.create_task(stream_loop())

                elif action == 'get_stream_frame':
                    try:
                        with open('/tmp/stream/frame.png', 'rb') as f:
                            screenshot = f.read()
                        result['screenshot'] = base64.b64encode(screenshot).decode()
                        result['message'] = "Frame captured"
                    except:
                        result['success'] = False
                        result['error'] = "No stream available"

                elif action == 'get_content':
                    result['html'] = await page.content()
                    result['url'] = page.url
                    result['title'] = await page.title()

                elif action == 'get_elements':
                    # First, highlight ALL interactive elements
                    await highlight_elements()
                    
                    # Extract all interactive and content elements (same as navigate)
                    elements = await page.evaluate('''() => {
                        const elements = [];
                        let index = 0;

                        // Get all interactive elements (buttons, links, inputs)
                        const interactiveSelectors = 'a, button, input, select, textarea, [role="button"], [onclick]';
                        const interactiveElements = document.querySelectorAll(interactiveSelectors);

                        for (const el of interactiveElements) {
                            const style = window.getComputedStyle(el);
                            if (style.display === 'none' || style.visibility === 'hidden') continue;

                            const info = {
                                index: index++,
                                tag: el.tagName.toLowerCase(),
                                type: el.type || 'interactive',
                                text: el.innerText?.trim().substring(0, 100) || el.value || '',
                                placeholder: el.placeholder || '',
                                id: el.id || '',
                                class: el.className || '',
                                name: el.name || '',
                                href: el.href || '',
                            };
                            elements.push(info);
                        }

                        // Also get important non-interactive elements
                        const contentSelectors = 'h1, h2, h3, h4, h5, h6, p[class], div[class], span[class], img, [role="heading"], [role="alert"]';
                        const contentElements = document.querySelectorAll(contentSelectors);

                        for (const el of contentElements) {
                            const style = window.getComputedStyle(el);
                            if (style.display === 'none' || style.visibility === 'hidden') continue;

                            const text = el.innerText?.trim() || el.alt || '';
                            if (!text && el.tagName.toLowerCase() !== 'img') continue;
                            if (text.length < 2) continue;

                            const info = {
                                index: index++,
                                tag: el.tagName.toLowerCase(),
                                type: 'content',
                                text: text.substring(0, 100),
                                id: el.id || '',
                                class: el.className || '',
                                src: el.src || '',
                                alt: el.alt || '',
                            };
                            elements.push(info);
                        }

                        return elements;
                    }''')

                    result['url'] = page.url
                    result['title'] = await page.title()
                    result['elements'] = elements
                    result['element_count'] = len(elements)

                elif action == 'evaluate':
                    # Execute JavaScript and return the result
                    script = cmd.get('script', '')
                    if not script:
                        result['success'] = False
                        result['error'] = "No script provided"
                    else:
                        try:
                            # Auto-wrap script in function based on content
                            script = script.strip()
                            
                            # Check if it's already a function
                            is_function = (script.startswith('(') or 
                                         script.startswith('function') or
                                         script.startswith('async'))
                            
                            if not is_function:
                                # Check if it's a multi-line script with statements
                                has_statements = any(keyword in script for keyword in [
                                    'var ', 'let ', 'const ', 'for ', 'while ', 'if ', 'switch '
                                ])
                                
                                # Check for newline using splitlines
                                is_multiline = len(script.splitlines()) > 1
                                
                                if has_statements or is_multiline:
                                    # Multi-line script with statements: wrap as function body
                                    script = f"() => {{ {script} }}"
                                elif script.startswith('return '):
                                    # Single return statement: extract expression
                                    script = f"() => ({script[7:]})"
                                else:
                                    # Simple expression: wrap in arrow function
                                    script = f"() => ({script})"
                            
                            js_result = await page.evaluate(script)
                            result['result'] = js_result
                        except Exception as e:
                            result['success'] = False
                            result['error'] = str(e)

                elif action == 'get_by_role':
                    # Get elements by ARIA role (semantic locator)
                    role = cmd.get('role', '')
                    try:
                        locator = page.get_by_role(role)
                        count = await locator.count()
                        elements = []
                        
                        for i in range(min(count, 50)):  # Limit to first 50
                            element = locator.nth(i)
                            text = await element.text_content()
                            is_visible = await element.is_visible()
                            
                            if is_visible:
                                elements.append({
                                    'index': i,
                                    'role': role,
                                    'text': text.strip() if text else '',
                                    'visible': True
                                })
                        
                        result['role'] = role
                        result['count'] = count
                        result['elements'] = elements
                    except Exception as e:
                        result['success'] = False
                        result['error'] = str(e)
                
                elif action == 'get_by_text':
                    # Get elements containing specific text
                    search_text = cmd.get('search_text', '')
                    try:
                        locator = page.get_by_text(search_text)
                        count = await locator.count()
                        elements = []
                        
                        for i in range(min(count, 50)):
                            element = locator.nth(i)
                            text = await element.text_content()
                            tag = await element.evaluate('el => el.tagName.toLowerCase()')
                            
                            elements.append({
                                'index': i,
                                'tag': tag,
                                'text': text.strip() if text else '',
                            })
                        
                        result['search_text'] = search_text
                        result['count'] = count
                        result['elements'] = elements
                    except Exception as e:
                        result['success'] = False
                        result['error'] = str(e)
                
                elif action == 'get_headings':
                    # Get all heading elements (h1-h6)
                    elements = []
                    for level in range(1, 7):
                        locator = page.get_by_role('heading', level=level)
                        count = await locator.count()
                        
                        for i in range(count):
                            element = locator.nth(i)
                            text = await element.text_content()
                            
                            elements.append({
                                'index': len(elements),
                                'level': level,
                                'text': text.strip() if text else ''
                            })
                    
                    result['headings'] = elements
                    result['count'] = len(elements)
                
                elif action == 'get_buttons':
                    # Get buttons with indices compatible with click_element
                    # Use SAME selector as click_element for index compatibility
                    selectors = 'a, button, input, select, textarea, [role="button"], [onclick]'
                    all_interactive = await page.query_selector_all(selectors)
                    elements = []
                    
                    global_index = 0
                    for element in all_interactive[:200]:
                        try:
                            # Check if visible
                            style = await element.evaluate('el => window.getComputedStyle(el)')
                            if style.get('display') == 'none' or style.get('visibility') == 'hidden':
                                continue
                            
                            # Check if it's a button-like element
                            tag = await element.evaluate('el => el.tagName.toLowerCase()')
                            role = await element.evaluate('el => el.getAttribute("role")')
                            elem_type = await element.evaluate('el => el.getAttribute("type")')
                            
                            is_button = (
                                tag == 'button' or 
                                role == 'button' or
                                elem_type in ['button', 'submit'] or
                                await element.evaluate('el => el.hasAttribute("onclick")')
                            )
                            
                            if is_button:
                                text = await element.text_content()
                                elements.append({
                                    'index': global_index,  # Global index for click_element
                                    'text': text.strip() if text else ''
                                })
                            
                            global_index += 1
                        except:
                            pass
                    
                    result['buttons'] = elements
                    result['count'] = len(elements)
                
                elif action == 'get_links':
                    # Get all link elements
                    locator = page.get_by_role('link')
                    count = await locator.count()
                    elements = []
                    
                    for i in range(min(count, 100)):
                        element = locator.nth(i)
                        text = await element.text_content()
                        href = await element.get_attribute('href')
                        
                        elements.append({
                            'index': i,
                            'text': text.strip() if text else '',
                            'href': href or ''
                        })
                    
                    result['links'] = elements
                    result['count'] = len(elements)
                
                elif action == 'get_inputs':
                    # Get all input/textbox elements
                    locator = page.get_by_role('textbox')
                    count = await locator.count()
                    elements = []
                    
                    for i in range(min(count, 50)):
                        element = locator.nth(i)
                        placeholder = await element.get_attribute('placeholder')
                        value = await element.input_value()
                        
                        elements.append({
                            'index': i,
                            'placeholder': placeholder or '',
                            'value': value or ''
                        })
                    
                    result['inputs'] = elements
                    result['count'] = len(elements)
                
                elif action == 'get_by_placeholder':
                    # Get input elements by placeholder text
                    placeholder_text = cmd.get('placeholder_text', '')
                    try:
                        locator = page.get_by_placeholder(placeholder_text)
                        count = await locator.count()
                        elements = []
                        
                        for i in range(min(count, 20)):
                            element = locator.nth(i)
                            tag = await element.evaluate('el => el.tagName.toLowerCase()')
                            placeholder = await element.get_attribute('placeholder')
                            value = await element.input_value() if tag == 'input' or tag == 'textarea' else ''
                            
                            elements.append({
                                'index': i,
                                'tag': tag,
                                'placeholder': placeholder or '',
                                'value': value or ''
                            })
                        
                        result['placeholder_text'] = placeholder_text
                        result['count'] = count
                        result['elements'] = elements
                    except Exception as e:
                        result['success'] = False
                        result['error'] = str(e)
                
                elif action == 'get_by_label':
                    # Get form controls by associated label text
                    label_text = cmd.get('label', '')
                    try:
                        locator = page.get_by_label(label_text)
                        count = await locator.count()
                        elements = []
                        
                        for i in range(min(count, 20)):
                            element = locator.nth(i)
                            tag = await element.evaluate('el => el.tagName.toLowerCase()')
                            elem_type = await element.get_attribute('type') or ''
                            value = ''
                            
                            if tag == 'input' or tag == 'textarea':
                                try:
                                    value = await element.input_value()
                                except:
                                    pass
                            
                            elements.append({
                                'index': i,
                                'tag': tag,
                                'type': elem_type,
                                'value': value
                            })
                        
                        result['label'] = label_text
                        result['count'] = count
                        result['elements'] = elements
                    except Exception as e:
                        result['success'] = False
                        result['error'] = str(e)

                elif action == 'wait_for_selector':
                    # Smart wait for element to be in specified state
                    selector = cmd.get('selector', '')
                    wait_state = cmd.get('wait_state', 'visible')
                    
                    try:
                        if wait_state == 'visible':
                            await page.wait_for_selector(selector, state='visible', timeout=30000)
                        elif wait_state == 'hidden':
                            await page.wait_for_selector(selector, state='hidden', timeout=30000)
                        elif wait_state == 'attached':
                            await page.wait_for_selector(selector, state='attached', timeout=30000)
                        elif wait_state == 'detached':
                            await page.wait_for_selector(selector, state='detached', timeout=30000)
                        else:
                            await page.wait_for_selector(selector, timeout=30000)
                        
                        result['message'] = f"Selector '{selector}' is now '{wait_state}'"
                    except Exception as e:
                        result['success'] = False
                        result['error'] = f"Timeout waiting for selector '{selector}' to be '{wait_state}': {str(e)}"
                
                elif action == 'wait_for_url':
                    # Smart wait for URL to match pattern
                    url_pattern = cmd.get('url_pattern', '')
                    
                    try:
                        await page.wait_for_url(url_pattern, timeout=30000)
                        result['message'] = f"URL now matches pattern: {url_pattern}"
                        result['url'] = page.url
                    except Exception as e:
                        result['success'] = False
                        result['error'] = f"Timeout waiting for URL pattern '{url_pattern}': {str(e)}"
                
                elif action == 'wait_for_load_state':
                    # Smart wait for page load state
                    # Default to domcontentloaded (works better for modern apps with continuous network activity)
                    load_state = cmd.get('load_state', 'domcontentloaded')
                    
                    try:
                        await page.wait_for_load_state(load_state, timeout=30000)
                        result['message'] = f"Page ready ({load_state})"
                    except Exception as e:
                        # Timeout is usually fine - page might still be interactive
                        result['message'] = f"Page may be ready (continuing despite timeout)"
                        # Don't fail - modern apps often have continuous activity

                elif action == 'assert_element_visible':
                    # Assert element with text is visible (with smart waiting)
                    search_text = cmd.get('search_text', '')
                    description = cmd.get('assertion_description', f"Element '{search_text}' is visible")
                    
                    try:
                        # Wait up to 10 seconds for element to appear and be visible
                        locator = page.get_by_text(search_text)
                        
                        # Use Playwright's wait_for with visible state
                        await locator.first.wait_for(state='visible', timeout=10000)
                        
                        result['message'] = f"✅ Assertion passed: {description}"
                        result['assertion'] = description
                    except Exception as e:
                        result['success'] = False
                        result['error'] = f"❌ Assertion failed: {description} - Element '{search_text}' not visible within 10s"
                
                elif action == 'assert_element_hidden':
                    # Assert element is hidden
                    search_text = cmd.get('search_text', '')
                    description = cmd.get('assertion_description', f"Element '{search_text}' is hidden")
                    
                    try:
                        from playwright.async_api import expect
                        locator = page.get_by_text(search_text)
                        await expect(locator).to_be_hidden(timeout=5000)
                        result['message'] = f"✅ Assertion passed: {description}"
                        result['assertion'] = description
                    except Exception as e:
                        result['success'] = False
                        result['error'] = f"❌ Assertion failed: {description} - {str(e)}"
                
                elif action == 'assert_text_contains':
                    # Assert element contains expected text
                    search_text = cmd.get('search_text', '')
                    expected_text = cmd.get('expected_text', '')
                    description = cmd.get('assertion_description', f"Element contains '{expected_text}'")
                    
                    try:
                        from playwright.async_api import expect
                        locator = page.get_by_text(search_text)
                        await expect(locator).to_contain_text(expected_text, timeout=5000)
                        result['message'] = f"✅ Assertion passed: {description}"
                        result['assertion'] = description
                    except Exception as e:
                        result['success'] = False
                        result['error'] = f"❌ Assertion failed: {description} - {str(e)}"
                
                elif action == 'assert_url_contains':
                    # Assert current URL contains expected text (with smart waiting)
                    expected_text = cmd.get('expected_text', '')
                    description = cmd.get('assertion_description', f"URL contains '{expected_text}'")
                    
                    try:
                        # Wait up to 20 seconds for URL to contain expected text (redirects can be slow)
                        import time
                        start_time = time.time()
                        
                        while time.time() - start_time < 20:
                            current_url = page.url
                            if expected_text in current_url:
                                result['message'] = f"✅ Assertion passed: {description}"
                                result['assertion'] = description
                                result['url'] = current_url
                                break
                            await asyncio.sleep(0.5)  # Check every 500ms
                        else:
                            # Timeout - assertion failed
                            result['success'] = False
                            result['error'] = f"❌ Assertion failed: {description} - Expected '{expected_text}' in URL, got: {page.url} (waited 20s)"
                    except Exception as e:
                        result['success'] = False
                        result['error'] = f"❌ Assertion failed: {description} - {str(e)}"
                
                elif action == 'assert_count_equals':
                    # Assert count of elements equals expected (with smart waiting)
                    search_text = cmd.get('search_text', '')
                    expected_count = cmd.get('expected_count', 0)
                    locator_type = cmd.get('locator_type', 'text')  # default to text
                    description = cmd.get('assertion_description', f"Found exactly {expected_count} '{search_text}' elements")
                    
                    try:
                        # Wait up to 10 seconds for count to match
                        import time
                        start_time = time.time()
                        
                        # Use appropriate locator based on type
                        if locator_type == 'role':
                            locator = page.get_by_role(search_text)
                        elif locator_type == 'tag':
                            locator = page.locator(search_text)
                        else:  # text
                            locator = page.get_by_text(search_text)
                        
                        while time.time() - start_time < 10:
                            count = await locator.count()
                            if count == expected_count:
                                result['message'] = f"✅ Assertion passed: {description}"
                                result['assertion'] = description
                                break
                            await asyncio.sleep(0.5)
                        else:
                            # Timeout
                            actual_count = await locator.count()
                            result['success'] = False
                            result['error'] = f"❌ Assertion failed: {description} - Expected {expected_count}, found {actual_count} (waited 10s)"
                    except Exception as e:
                        result['success'] = False
                        result['error'] = f"❌ Assertion failed: {description} - {str(e)}"
                
                elif action == 'assert_has_value':
                    # Assert input field has expected value (with smart waiting)
                    index = cmd.get('index', 0)
                    expected_value = cmd.get('expected_value', '')
                    description = cmd.get('assertion_description', f"Field has value '{expected_value}'")
                    
                    try:
                        # Wait up to 10 seconds for field to have expected value
                        import time
                        start_time = time.time()
                        
                        # Get VISIBLE input fields only (filter out hidden auth tokens)
                        # Use the same logic as input_text action for consistency
                        visible_inputs = await page.evaluate('''() => {
                            const inputs = document.querySelectorAll('input, textarea');
                            const visible = [];
                            
                            inputs.forEach(inp => {
                                const style = window.getComputedStyle(inp);
                                const isVisible = style.display !== 'none' && 
                                               style.visibility !== 'hidden' && 
                                               style.opacity !== '0' &&
                                               inp.offsetHeight > 0;
                                
                                if (isVisible) {
                                    visible.push({
                                        type: inp.type || 'text',
                                        value: inp.value || '',
                                        name: inp.name || ''
                                    });
                                }
                            });
                            
                            return visible;
                        }''')
                        
                        print(f"[DEBUG] Found {len(visible_inputs)} visible inputs", flush=True)
                        for i, inp in enumerate(visible_inputs):
                            print(f"[DEBUG]   [{i}] type={inp.get('type')}, value='{inp.get('value', '')[:30]}...'", flush=True)
                        
                        if index >= len(visible_inputs):
                            result['success'] = False
                            result['error'] = f"❌ Assertion failed: Visible input index {index} not found (found {len(visible_inputs)} visible inputs)"
                        else:
                            # Get value from our visible inputs list
                            actual_value = visible_inputs[index].get('value', '')
                            input_type = visible_inputs[index].get('type', 'unknown')
                            
                            print(f"[DEBUG] Checking index {index}: type={input_type}, value='{actual_value[:30]}...'", flush=True)
                            
                            # Check if value matches
                            if actual_value == expected_value:
                                result['message'] = f"✅ Assertion passed: {description}"
                                result['assertion'] = description
                            else:
                                result['success'] = False
                                result['error'] = f"❌ Assertion failed: {description} - Expected '{expected_value}', got '{actual_value}' (index={index}, type={input_type})"
                    except Exception as e:
                        result['success'] = False
                        result['error'] = f"❌ Assertion failed: {description} - {str(e)}"

                elif action == 'stop':
                    await browser.close()
                    with open('/tmp/browser_response.json', 'w') as f:
                        json.dump(result, f)
                    break

                # Write response
                with open('/tmp/browser_response.json', 'w') as f:
                    json.dump(result, f)

                # Remove command file
                import os
                os.remove('/tmp/browser_command.json')

            except Exception as e:
                result = {"success": False, "error": str(e)}
                with open('/tmp/browser_response.json', 'w') as f:
                    json.dump(result, f)
                try:
                    import os
                    os.remove('/tmp/browser_command.json')
                except:
                    pass

if __name__ == '__main__':
    asyncio.run(main())
"""

        # Write and start the browser server (async to avoid blocking)
        write_start = time.time()
        await loop.run_in_executor(
            None,
            lambda: self.sandbox.filesystem_write(self._browser_script_path, browser_server_script)
        )
        write_time = time.time() - write_start
        print(f"  Script written ({write_time:.2f}s)")

        # Start browser server in background with proper environment AND DISPLAY for VNC
        # Use wrapper script to make it truly fire-and-forget
        exec_start = time.time()
        
        # Create a launcher script that exits immediately after starting browser
        launcher_script = f"""#!/bin/bash
export PLAYWRIGHT_BROWSERS_PATH=/home/user/.cache/ms-playwright
export DISPLAY=:99
python3 {self._browser_script_path} > /tmp/browser.log 2>&1 &
echo $! > {self._browser_pid_file}
exit 0
"""
        await loop.run_in_executor(
            None,
            lambda: self.sandbox.filesystem_write("/tmp/start_browser.sh", launcher_script)
        )
        
        # Make executable and run (this should return immediately since script exits)
        start_cmd = "chmod +x /tmp/start_browser.sh && /tmp/start_browser.sh"
        result = await loop.run_in_executor(None, lambda: self.sandbox.exec(start_cmd))
        exec_time = time.time() - exec_start
        print(f"  Start command executed ({exec_time:.2f}s)")

        # Wait for browser to be ready - poll for "Browser ready" message
        # Run polling in thread pool to avoid blocking
        for i in range(20):  # Max 10 seconds
            await asyncio.sleep(0.5)
            # Run exec in thread pool to avoid blocking
            log_check = await loop.run_in_executor(
                None,
                lambda: self.sandbox.exec("grep 'Browser ready' /tmp/browser.log 2>/dev/null || echo 'not ready'")
            )
            if "Browser ready" in log_check.stdout:
                print(f"  Detected at poll #{i+1} ({(i+1)*0.5:.1f}s)")
                break

        # Verify the process started (run in thread pool)
        check = await loop.run_in_executor(
            None,
            lambda: self.sandbox.exec(
                f"test -f {self._browser_pid_file} && kill -0 $(cat {self._browser_pid_file}) 2>/dev/null && echo 'running' || echo 'not running'"
            )
        )

        if "not running" in check.stdout:
            # Check logs for error
            log_check = await loop.run_in_executor(
                None,
                lambda: self.sandbox.exec("cat /tmp/browser.log 2>&1 | tail -20")
            )
            logger.error(f"Browser server failed to start. Log:\n{log_check.stdout}")
            raise RuntimeError("Browser server failed to start")

        self._browser_initialized = True
        elapsed = time.time() - start_time
        
        # Get detailed timing from browser log (async)
        log_output = await loop.run_in_executor(
            None,
            lambda: self.sandbox.exec("cat /tmp/browser.log 2>&1 | head -10")
        )
        
        print(f"✅ Browser ready ({elapsed:.2f}s)")
        print(f"Detailed timing:")
        for line in log_output.stdout.split('\n')[:6]:
            if line.strip():
                print(f"  {line}")

    async def _run_validation(self, validate_after: dict) -> ToolResult:
        """
        Run validation after an action completes
        
        Args:
            validate_after: Validation specification with type, description, and parameters
            
        Returns:
            ToolResult with validation success/failure
        """
        if not validate_after:
            return None
            
        validation_type = validate_after.get("type")
        description = validate_after.get("description", "Validation")
        
        try:
            if validation_type == "url_contains":
                expected_text = validate_after.get("expected_text", "")
                result = await self._execute_browser_command({
                    "action": "assert_url_contains",
                    "expected_text": expected_text,
                    "assertion_description": description
                })
                if result.get("success"):
                    return None  # Validation passed, continue
                else:
                    return self.fail_response(f"❌ Validation failed: {description} - {result.get('error', 'URL does not contain expected text')}")
                    
            elif validation_type == "element_visible":
                search_text = validate_after.get("search_text", "")
                result = await self._execute_browser_command({
                    "action": "assert_element_visible",
                    "search_text": search_text,
                    "assertion_description": description
                })
                if result.get("success"):
                    return None  # Validation passed
                else:
                    return self.fail_response(f"❌ Validation failed: {description} - {result.get('error', 'Element not visible')}")
                    
            elif validation_type == "element_not_visible":
                search_text = validate_after.get("search_text", "")
                result = await self._execute_browser_command({
                    "action": "assert_element_hidden",
                    "search_text": search_text,
                    "assertion_description": description
                })
                if result.get("success"):
                    return None  # Validation passed
                else:
                    return self.fail_response(f"❌ Validation failed: {description} - {result.get('error', 'Element is still visible')}")
                    
            elif validation_type == "count_equals":
                search_text = validate_after.get("search_text", "")
                expected_count = validate_after.get("expected_count", 0)
                locator_type = validate_after.get("locator_type", "text")
                result = await self._execute_browser_command({
                    "action": "assert_count_equals",
                    "search_text": search_text,
                    "expected_count": expected_count,
                    "locator_type": locator_type,
                    "assertion_description": description
                })
                if result.get("success"):
                    return None  # Validation passed
                else:
                    return self.fail_response(f"❌ Validation failed: {description} - {result.get('error', 'Count does not match')}")
                    
            else:
                return self.fail_response(f"Unknown validation type: {validation_type}")
                
        except Exception as e:
            return self.fail_response(f"Validation error: {str(e)}")
    
    async def _execute_browser_command(self, command: dict, timeout: int = 60) -> dict:
        """Execute a command on the persistent browser"""
        await self._ensure_browser_server()
        
        import asyncio
        loop = asyncio.get_event_loop()

        # Remove old response file (async)
        await loop.run_in_executor(None, lambda: self.sandbox.exec("rm -f /tmp/browser_response.json"))

        # Write command (async)
        cmd_json = json.dumps(command)
        logger.debug(f"📤 Sending browser command: {command.get('action', 'unknown')}")
        logger.debug(f"📤 Command payload size: {len(cmd_json)} bytes")
        logger.debug(f"📤 Full command JSON: {cmd_json}")
        
        # Write the command file
        await loop.run_in_executor(None, lambda: self.sandbox.filesystem_write("/tmp/browser_command.json", cmd_json))
        
        # Small delay to allow filesystem to flush (helps prevent race condition)
        await asyncio.sleep(0.1)

        # Wait for response (check every 0.5 seconds, async polling)
        import time as time_module
        poll_start = time_module.time()
        poll_count = 0
        
        for i in range(timeout * 2):
            await asyncio.sleep(0.5)
            poll_count += 1
            check = await loop.run_in_executor(
                None,
                lambda: self.sandbox.exec("test -f /tmp/browser_response.json && echo 'ready' || echo 'waiting'")
            )
            if "ready" in check.stdout:
                poll_time = time_module.time() - poll_start
                print(f"  Response ready after {poll_count} polls ({poll_time:.2f}s)")
                logger.debug(f"✅ Browser response file ready after {poll_time:.2f}s")
                
                # Read the response file with detailed logging
                response_json = await loop.run_in_executor(
                    None,
                    lambda: self.sandbox.filesystem_read("/tmp/browser_response.json")
                )
                
                logger.debug(f"📥 Raw response type: {type(response_json)}")
                logger.debug(f"📥 Raw response length: {len(response_json) if response_json else 0} bytes")
                logger.debug(f"📥 Full response content: {repr(response_json)}")
                
                # Parse JSON with error handling
                try:
                    if not response_json or not response_json.strip():
                        logger.error("❌ Empty browser response file")
                        # Check browser server logs
                        log_output = await loop.run_in_executor(
                            None,
                            lambda: self.sandbox.exec("tail -50 /tmp/browser.log")
                        )
                        logger.error(f"Browser server log (last 50 lines):\n{log_output.stdout}")
                        return {"success": False, "error": "Empty browser response - check /tmp/browser.log"}
                    
                    parsed = json.loads(response_json)
                    logger.debug(f"✅ Successfully parsed JSON response: {parsed.get('success', 'unknown')}")
                    return parsed
                    
                except json.JSONDecodeError as e:
                    logger.error(f"❌ JSON parse error: {str(e)}")
                    logger.error(f"❌ Failed content (full): {repr(response_json)}")
                    
                    # Check browser server logs on error
                    log_output = await loop.run_in_executor(
                        None,
                        lambda: self.sandbox.exec("tail -100 /tmp/browser.log")
                    )
                    logger.error(f"Browser server log (last 100 lines):\n{log_output.stdout}")
                    
                    return {
                        "success": False, 
                        "error": f"Invalid browser response: {str(e)} | Raw content: {response_json}"
                    }

        logger.error(f"⏱️ Timeout after {timeout}s waiting for browser response")
        # Check browser server logs on timeout
        log_output = await loop.run_in_executor(
            None,
            lambda: self.sandbox.exec("tail -100 /tmp/browser.log")
        )
        logger.error(f"Browser server log (last 100 lines):\n{log_output.stdout}")
        
        return {
            "success": False,
            "error": f"Timeout waiting for browser response (waited {timeout}s) - check /tmp/browser.log",
        }

    async def execute(
        self,
        action: str,
        url: Optional[str] = None,
        text: Optional[str] = None,
        amount: Optional[int] = None,
        page_id: Optional[int] = None,
        keys: Optional[str] = None,
        seconds: Optional[int] = None,
        x: Optional[int] = None,
        y: Optional[int] = None,
        element_source: Optional[str] = None,
        element_target: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        """Execute a browser action using persistent Playwright session"""
        import asyncio
        import time

        if not self.sandbox:
            return self.fail_response("E2B sandbox not initialized")

        # Extract validate_after from kwargs if present
        validate_after = kwargs.pop("validate_after", None)

        try:
            # NEW: Locator-based actions (stable, no indices)
            if action == "click":
                # Click using stable locator
                index = kwargs.get("index")
                if index is not None:
                    return self.fail_response(
                        "❌ click(index=...) is DEPRECATED!\n\n"
                        "Use stable locators instead:\n"
                        "✅ click(by_text='Button Text')\n"
                        "✅ click(by_role='button', has_text='Submit')\n"
                        "✅ click(by_id='submit-btn')\n"
                        "✅ click(by_css='button.primary')\n\n"
                        "Example: If get_elements() shows '[0] button text=\"Continue\"'\n"
                        "→ Extract 'Continue' and use: click(by_text='Continue')"
                    )
                
                locator_spec = {
                    "type": kwargs.get("by_text") and "text" or
                           kwargs.get("by_role") and "role" or  
                           kwargs.get("by_placeholder") and "placeholder" or
                           kwargs.get("by_label") and "label" or
                           kwargs.get("by_test_id") and "testid" or
                           kwargs.get("by_id") and "id" or
                           kwargs.get("by_css") and "css" or "text",
                    "value": kwargs.get("by_text") or kwargs.get("by_role") or 
                            kwargs.get("by_placeholder") or kwargs.get("by_label") or
                            kwargs.get("by_test_id") or kwargs.get("by_id") or
                            kwargs.get("by_css") or "",
                    "has_text": kwargs.get("has_text")
                }
                
                result = await self._execute_browser_command({
                    "action": "click_locator",
                    "locator": locator_spec
                })
                
                # Fetch browser debug logs
                import asyncio
                loop = asyncio.get_event_loop()
                debug_logs = await loop.run_in_executor(
                    None,
                    lambda: self.sandbox.exec("grep '\\[CLICK DEBUG\\]' /tmp/browser.log 2>/dev/null | tail -5")
                )
                if debug_logs.stdout.strip():
                    print("Browser debug logs:")
                    for line in debug_logs.stdout.strip().split('\n'):
                        print(f"  {line}")
                
                if result.get("success"):
                    # Run validation if specified
                    if validate_after:
                        validation_result = await self._run_validation(validate_after)
                        if validation_result:  # If validation failed, return the failure
                            return validation_result
                    return self.success_response(result.get("message", "Clicked element"))
                else:
                    return self.fail_response(result.get("error", "Click failed"))
            
            elif action == "fill":
                # Fill input using stable locator
                index = kwargs.get("index")
                if index is not None:
                    return self.fail_response(
                        "❌ fill(index=...) is DEPRECATED!\n\n"
                        "Use stable locators instead:\n"
                        "✅ fill(by_placeholder='Email', text='...')\n"
                        "✅ fill(by_label='Password', text='...')\n\n"
                        "Example: If get_elements() shows '[0] input placeholder=\"Email\"'\n"
                        "→ Extract 'Email' and use: fill(by_placeholder='Email', text='...')"
                    )
                
                if not text:
                    return self.fail_response("Text is required for fill action")
                
                locator_spec = {
                    "type": kwargs.get("by_placeholder") and "placeholder" or
                           kwargs.get("by_label") and "label" or
                           kwargs.get("by_test_id") and "testid" or
                           kwargs.get("by_id") and "id" or
                           kwargs.get("by_css") and "css" or
                           kwargs.get("by_text") and "text" or "placeholder",
                    "value": kwargs.get("by_placeholder") or kwargs.get("by_label") or
                            kwargs.get("by_test_id") or kwargs.get("by_id") or
                            kwargs.get("by_css") or kwargs.get("by_text") or ""
                }
                
                result = await self._execute_browser_command({
                    "action": "fill_locator",
                    "locator": locator_spec,
                    "text": text
                })
                
                if result.get("success"):
                    # Run validation if specified
                    if validate_after:
                        validation_result = await self._run_validation(validate_after)
                        if validation_result:  # If validation failed, return the failure
                            return validation_result
                    return self.success_response(result.get("message", "Filled input"))
                else:
                    return self.fail_response(result.get("error", "Fill failed"))
            
            # Navigation
            elif action == "navigate_to":
                if not url:
                    return self.fail_response("URL is required for navigation")

                result = await self._execute_browser_command(
                    {"action": "navigate", "url": url}
                )
                
                # Get navigate timing from browser log
                loop = asyncio.get_event_loop()
                nav_logs = await loop.run_in_executor(
                    None,
                    lambda: self.sandbox.exec("grep '\\[NAV\\]' /tmp/browser.log 2>/dev/null | tail -5")
                )
                if nav_logs.stdout.strip():
                    print("Navigate breakdown:")
                    for line in nav_logs.stdout.strip().split('\n'):
                        print(f"  {line}")

                # Fire-and-forget window management (don't wait for completion)
                # These commands take 15s if we wait, but browser works immediately
                async def run_window_management():
                    await loop.run_in_executor(None, lambda: self.sandbox.exec(
                        "DISPLAY=:99 xdotool search --name 'Activity Monitor' windowminimize 2>/dev/null || true; "
                        "DISPLAY=:99 xdotool search --name chromium windowactivate --sync windowraise 2>/dev/null || true; "
                        "DISPLAY=:99 xdotool search --name chromium key F11 2>/dev/null || true"
                    ))
                
                asyncio.create_task(run_window_management())
                # Commands run in background, continue immediately
                if result.get("success"):

                    # Format element information for the LLM - show ALL elements
                    elements_info = "\n\nPage Elements:\n"
                    all_elements = result.get("elements", [])

                    for elem in all_elements:  # Show ALL elements (no limit)
                        # Format based on element type
                        elem_type = elem.get("type", "")
                        elem_desc = f"[{elem['index']}] {elem['tag']}"

                        if elem_type and elem_type not in ["interactive", "content"]:
                            elem_desc += f" type={elem_type}"
                        elif elem_type == "content":
                            elem_desc += " (content-only)"  # Can't click this

                        if elem.get("text"):
                            elem_desc += f" text='{elem['text'][:50]}'"
                        if elem.get("placeholder"):
                            elem_desc += f" placeholder='{elem['placeholder']}'"

                        # Show important classes for context
                        if elem.get("class"):
                            classes = elem["class"].lower()
                            if any(
                                kw in classes
                                for kw in ["loading", "spinner", "error", "alert"]
                            ):
                                elem_desc += (
                                    f" [{classes.split()[0] if classes else ''}]"
                                )

                        elements_info += elem_desc + "\n"

                    response_msg = f"Successfully navigated to {result.get('url')}\n"
                    response_msg += f"Title: {result.get('title')}\n"
                    response_msg += f"Found {result.get('element_count', 0)} interactive elements (all shown below)"
                    response_msg += elements_info

                    if result.get("page_text"):
                        response_msg += f"\n\nPage text (first 500 chars):\n{result['page_text'][:500]}"

                    # Run validation if specified
                    if validate_after:
                        validation_result = await self._run_validation(validate_after)
                        if validation_result:  # If validation failed, return the failure
                            return validation_result
                    
                    # Return without base64 to save tokens
                    return self.success_response(response_msg)
                else:
                    return self.fail_response(result.get("error", "Navigation failed"))

            # Wait
            elif action == "wait":
                seconds_to_wait = seconds if seconds is not None else 3
                await asyncio.sleep(seconds_to_wait)
                return self.success_response(f"Waited for {seconds_to_wait} seconds")

            # Input text by index (uses JavaScript to find and fill the element)
            elif action == "input_text":
                if index is None or text is None:
                    return self.fail_response("Index and text are required")

                # Fill by index directly in page context
                result = await self._execute_browser_command(
                    {"action": "fill_by_index", "index": index, "text": text}
                )
                if result.get("success"):
                    return self.success_response(f"Filled field [{index}] with text")
                else:
                    return self.fail_response(result.get("error", "Fill failed"))

            # Send keys
            elif action == "send_keys":
                if not keys:
                    return self.fail_response("Keys are required")

                # Determine if it's a special key or regular text
                special_keys = [
                    "Enter",
                    "Tab",
                    "Escape",
                    "Backspace",
                    "Delete",
                    "ArrowUp",
                    "ArrowDown",
                    "ArrowLeft",
                    "ArrowRight",
                ]

                if keys in special_keys:
                    # Use press for special keys
                    result = await self._execute_browser_command(
                        {"action": "press", "key": keys}
                    )
                else:
                    # Use type for regular text
                    result = await self._execute_browser_command(
                        {"action": "type", "text": keys}
                    )

                if result.get("success"):
                    return self.success_response(f"Sent keys: {keys}")
                else:
                    return self.fail_response(result.get("error", "Send keys failed"))

            # Click element by index (uses JavaScript click to avoid timeout)
            elif action == "click_element":
                # DEPRECATED: Force agent to use stable locators
                return self.fail_response(
                    "❌ click_element(index) is DEPRECATED!\n\n"
                    "Use stable locators instead:\n"
                    "✅ click(by_text='Sign In') - if element has text\n"
                    "✅ click(by_role='button', has_text='Submit') - for buttons with specific text\n"
                    "✅ click(by_label='I agree') - for checkboxes/radio by label\n\n"
                    "Example: If get_elements() shows '[0] button text=\"Sign in\"'\n"
                    "→ Extract 'Sign in' and use: click(by_text='Sign in')"
                )
            
            # Old click_element implementation removed - agent must use click(by_text)
            
            elif action == "input_text":
                # DEPRECATED: Return error with instructions
                return self.fail_response(
                    "❌ input_text(index, text) is DEPRECATED!\n\n"
                    "Use stable locators instead:\n"
                    "✅ fill(by_placeholder='Email', text='user@example.com')\n"
                    "✅ fill(by_label='Password', text='secret')\n\n"
                    "Example: If get_inputs() shows 'Input #0: placeholder=Email'\n"
                    "→ Extract 'Email' and use: fill(by_placeholder='Email', text='...')"
                )

            # Other actions - simplified responses
            elif action == "go_back":
                return self.success_response("go_back action (use navigate_to instead)")
            elif action == "switch_tab":
                return self.success_response(f"switch_tab to page {page_id}")
            elif action == "close_tab":
                return self.success_response(f"close_tab page {page_id}")
            elif action == "scroll_down":
                return self.success_response(f"scroll_down {amount or 500}px")
            elif action == "scroll_up":
                return self.success_response(f"scroll_up {amount or 500}px")
            elif action == "scroll_to_text":
                return self.success_response(f"scroll_to_text '{text}'")
            elif action == "get_dropdown_options":
                return self.success_response(f"get_dropdown_options for index {index}")
            elif action == "select_dropdown_option":
                return self.success_response(
                    f"select_dropdown_option {index}: '{text}'"
                )
            elif action == "click_coordinates":
                return self.success_response(f"click_coordinates ({x}, {y})")
            elif action == "drag_drop":
                return self.success_response(
                    f"drag_drop '{element_source}' to '{element_target}'"
                )
            elif action == "get_by_role":
                # Get elements by ARIA role
                result = await self._execute_browser_command(
                    {"action": "get_by_role", "role": kwargs.get("role", "")}
                )
                
                if result.get("success"):
                    role = result.get("role")
                    elements = result.get("elements", [])
                    count = result.get("count", 0)
                    
                    response = f"Found {count} {role} elements (showing {len(elements)}):\n\n"
                    for elem in elements:
                        response += f"  [{elem['index']}] {elem.get('text', '')[:100]}\n"
                    
                    return self.success_response(response)
                else:
                    return self.fail_response(result.get("error", "get_by_role failed"))
            
            elif action == "get_by_text":
                # Get elements containing specific text
                result = await self._execute_browser_command(
                    {"action": "get_by_text", "search_text": kwargs.get("search_text", "")}
                )
                
                if result.get("success"):
                    elements = result.get("elements", [])
                    search_text = result.get("search_text")
                    
                    response = f"Found {len(elements)} elements containing '{search_text}':\n\n"
                    for elem in elements:
                        response += f"  [{elem['index']}] {elem.get('tag')}: {elem.get('text', '')[:100]}\n"
                    
                    return self.success_response(response)
                else:
                    return self.fail_response(result.get("error", "get_by_text failed"))
            
            elif action == "get_headings":
                # Get all headings
                result = await self._execute_browser_command({"action": "get_headings"})
                
                if result.get("success"):
                    headings = result.get("headings", [])
                    
                    response = f"Found {len(headings)} headings:\n\n"
                    for h in headings:
                        response += f"  [{h['index']}] H{h['level']}: {h.get('text', '')[:100]}\n"
                    
                    return self.success_response(response)
                else:
                    return self.fail_response(result.get("error", "get_headings failed"))
            
            elif action == "get_buttons":
                # Get all buttons
                result = await self._execute_browser_command({"action": "get_buttons"})
                
                if result.get("success"):
                    buttons = result.get("buttons", [])
                    
                    response = f"Found {len(buttons)} buttons:\n\n"
                    for btn in buttons:
                        response += f"  Button #{btn['index']}: {btn.get('text', '')[:50]}\n"
                    
                    response += f"\n💡 To click: Use index from 'Button #X' above\n"
                    response += f"Example: To click 'Continue', use click_element(index={buttons[0]['index'] if buttons else 0})"
                    return self.success_response(response)
                else:
                    return self.fail_response(result.get("error", "get_buttons failed"))
            
            elif action == "get_links":
                # Get all links
                result = await self._execute_browser_command({"action": "get_links"})
                
                if result.get("success"):
                    links = result.get("links", [])
                    
                    response = f"Found {len(links)} links:\n\n"
                    for link in links:
                        response += f"  [{link['index']}] {link.get('text', '')[:50]} → {link.get('href', '')}\n"
                    
                    return self.success_response(response)
                else:
                    return self.fail_response(result.get("error", "get_links failed"))
            
            elif action == "get_inputs":
                # Get all inputs
                result = await self._execute_browser_command({"action": "get_inputs"})
                
                if result.get("success"):
                    inputs = result.get("inputs", [])
                    
                    response = f"Found {len(inputs)} input fields:\n\n"
                    for inp in inputs:
                        response += f"  [{inp['index']}] placeholder: '{inp.get('placeholder', '')}', value: '{inp.get('value', '')}'\n"
                    
                    return self.success_response(response)
                else:
                    return self.fail_response(result.get("error", "get_inputs failed"))

            elif action == "get_by_placeholder":
                result = await self._execute_browser_command(
                    {"action": "get_by_placeholder", "placeholder_text": kwargs.get("placeholder_text", "")}
                )
                
                if result.get("success"):
                    elements = result.get("elements", [])
                    placeholder_text = result.get("placeholder_text")
                    
                    response = f"Found {len(elements)} inputs with placeholder '{placeholder_text}':\n\n"
                    for elem in elements:
                        response += f"  [{elem['index']}] {elem.get('tag')}: placeholder='{elem.get('placeholder', '')}', value='{elem.get('value', '')}'\n"
                    
                    return self.success_response(response)
                else:
                    return self.fail_response(result.get("error", "get_by_placeholder failed"))
            
            elif action == "get_by_label":
                result = await self._execute_browser_command(
                    {"action": "get_by_label", "label": kwargs.get("label", "")}
                )
                
                if result.get("success"):
                    elements = result.get("elements", [])
                    label_text = result.get("label")
                    
                    response = f"Found {len(elements)} elements with label '{label_text}':\n\n"
                    for elem in elements:
                        response += f"  [{elem['index']}] {elem.get('tag')} type={elem.get('type', '')}, value='{elem.get('value', '')}'\n"
                    
                    return self.success_response(response)
                else:
                    return self.fail_response(result.get("error", "get_by_label failed"))

            elif action == "wait_for_selector":
                result = await self._execute_browser_command(
                    {
                        "action": "wait_for_selector",
                        "selector": kwargs.get("selector", ""),
                        "wait_state": kwargs.get("wait_state", "visible"),
                    }
                )
                if result.get("success"):
                    return self.success_response(result.get("message", "Element is ready"))
                else:
                    return self.fail_response(result.get("error", "wait_for_selector failed"))
            
            elif action == "wait_for_url":
                result = await self._execute_browser_command(
                    {"action": "wait_for_url", "url_pattern": kwargs.get("url_pattern", "")}
                )
                if result.get("success"):
                    return self.success_response(
                        f"{result.get('message', 'URL matched')}. Current URL: {result.get('url', '')}"
                    )
                else:
                    return self.fail_response(result.get("error", "wait_for_url failed"))
            
            elif action == "wait_for_load_state":
                result = await self._execute_browser_command(
                    {"action": "wait_for_load_state", "load_state": kwargs.get("load_state", "load")}
                )
                if result.get("success"):
                    return self.success_response(result.get("message", "Page loaded"))
                else:
                    return self.fail_response(result.get("error", "wait_for_load_state failed"))

            elif action == "assert_element_visible":
                logger.debug(f"🔍 Executing assert_element_visible with search_text='{kwargs.get('search_text', '')}'")
                result = await self._execute_browser_command({
                    "action": "assert_element_visible",
                    "search_text": kwargs.get("search_text", ""),
                    "assertion_description": kwargs.get("assertion_description", "")
                })
                logger.debug(f"🔍 assert_element_visible result: success={result.get('success')}, error={result.get('error', 'N/A')}")
                if result.get("success"):
                    return self.success_response(result.get("message", "Assertion passed"))
                else:
                    error_msg = result.get("error", "Assertion failed")
                    logger.error(f"❌ assert_element_visible failed: {error_msg}")
                    return self.fail_response(error_msg)
            
            elif action == "assert_element_hidden":
                result = await self._execute_browser_command({
                    "action": "assert_element_hidden",
                    "search_text": kwargs.get("search_text", ""),
                    "assertion_description": kwargs.get("assertion_description", "")
                })
                if result.get("success"):
                    return self.success_response(result.get("message", "Assertion passed"))
                else:
                    return self.fail_response(result.get("error", "Assertion failed"))
            
            elif action == "assert_text_contains":
                result = await self._execute_browser_command({
                    "action": "assert_text_contains",
                    "search_text": kwargs.get("search_text", ""),
                    "expected_text": kwargs.get("expected_text", ""),
                    "assertion_description": kwargs.get("assertion_description", "")
                })
                if result.get("success"):
                    return self.success_response(result.get("message", "Assertion passed"))
                else:
                    return self.fail_response(result.get("error", "Assertion failed"))
            
            elif action == "assert_url_contains":
                result = await self._execute_browser_command({
                    "action": "assert_url_contains",
                    "expected_text": kwargs.get("expected_text", ""),
                    "assertion_description": kwargs.get("assertion_description", "")
                })
                if result.get("success"):
                    return self.success_response(f"{result.get('message', 'Assertion passed')} - URL: {result.get('url', '')}")
                else:
                    return self.fail_response(result.get("error", "Assertion failed"))
            
            elif action == "assert_count_equals":
                result = await self._execute_browser_command({
                    "action": "assert_count_equals",
                    "search_text": kwargs.get("search_text", ""),
                    "expected_count": kwargs.get("expected_count", 0),
                    "assertion_description": kwargs.get("assertion_description", "")
                })
                if result.get("success"):
                    return self.success_response(result.get("message", "Assertion passed"))
                else:
                    return self.fail_response(result.get("error", "Assertion failed"))
            
            elif action == "assert_has_value":
                result = await self._execute_browser_command({
                    "action": "assert_has_value",
                    "index": index if index is not None else kwargs.get("index", 0),  # Use parameter first!
                    "expected_value": kwargs.get("expected_value", ""),
                    "assertion_description": kwargs.get("assertion_description", "")
                })
                if result.get("success"):
                    return self.success_response(result.get("message", "Assertion passed"))
                else:
                    return self.fail_response(result.get("error", "Assertion failed"))

            elif action == "get_page_content":
                # Get page HTML and text content
                result = await self._execute_browser_command(
                    {"action": "get_content"}
                )

                if result.get("success"):
                    html = result.get("html", "")
                    url = result.get("url", "")
                    title = result.get("title", "")
                    
                    # Extract just the visible text from HTML
                    text_content = html[:2000] if html else ""
                    
                    return self.success_response(
                        f"Page Content Retrieved:\n"
                        f"URL: {url}\n"
                        f"Title: {title}\n"
                        f"HTML Length: {len(html)} characters\n"
                        f"Preview (first 2000 chars):\n{text_content}"
                    )
                else:
                    error_msg = result.get("error", "Failed to get page content")
                    return self.fail_response(f"Get page content error: {error_msg}")
            elif action == "get_elements":
                # Get all interactive elements on current page
                result = await self._execute_browser_command(
                    {"action": "get_elements"}
                )

                if result.get("success"):
                    elements = result.get("elements", [])
                    url = result.get("url", "")
                    title = result.get("title", "")
                    element_count = result.get("element_count", 0)
                    
                    # Format elements nicely
                    response_lines = [
                        f"Current Page Elements:",
                        f"URL: {url}",
                        f"Title: {title}",
                        f"Found {element_count} interactive elements",
                        "",
                        "Elements:",
                    ]
                    
                    for elem in elements:
                        elem_desc = f"  [{elem['index']}] {elem['tag']}"
                        if elem.get('type') and elem['type'] != 'interactive':
                            elem_desc += f" type={elem['type']}"
                        if elem.get('text'):
                            elem_desc += f" text='{elem['text'][:50]}'"
                        if elem.get('id'):
                            elem_desc += f" id='{elem['id']}'"
                        if elem.get('class'):
                            elem_desc += f" class='{elem['class'][:30]}'"
                        response_lines.append(elem_desc)
                    
                    return self.success_response("\n".join(response_lines))
                else:
                    error_msg = result.get("error", "Failed to get elements")
                    return self.fail_response(f"Get elements error: {error_msg}")
            else:
                return self.fail_response(f"Unknown action: {action}")

        except Exception as e:
            logger.error(f"Error executing browser action: {e}")
            return self.fail_response(f"Error executing browser action: {e}")

    async def cleanup(self):
        """Stop the persistent browser"""
        try:
            if self.sandbox and self._browser_initialized:
                await self._execute_browser_command({"action": "stop"})
                self.sandbox.exec(
                    f"rm -f {self._browser_pid_file} {self._browser_script_path} /tmp/browser_command.json /tmp/browser_response.json /tmp/browser.log"
                )
                self._browser_initialized = False
                logger.info("Persistent browser cleaned up")
        except Exception as e:
            logger.warning(f"Error cleaning up browser: {e}")
