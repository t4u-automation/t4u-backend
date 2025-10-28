"""
Persistent Selenium WebDriver Server for E2B Sandbox
Keeps WebDriver alive and processes commands via JSON files
Similar architecture to persistent_browser.py (Playwright)
"""

import json
import sys
import time
import traceback

# Install Selenium BEFORE importing (avoid import error)
try:
    import selenium

    print("Selenium already installed", flush=True)
except ImportError:
    print("Installing Selenium...", flush=True)
    import subprocess

    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "selenium"])
    print("Selenium installed successfully", flush=True)

# Now import Selenium modules (after installation)
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def main():
    driver = None

    try:
        print("Starting Selenium server...", flush=True)

        # Set DISPLAY to use Xvfb (VNC visible)
        import os

        os.environ["DISPLAY"] = ":99"
        print("DISPLAY set to :99 (VNC visible)", flush=True)

        # Configure Chrome options - HEADED mode for VNC visibility
        chrome_options = Options()
        # chrome_options.add_argument("--headless")  # ← REMOVED! Run in headed mode
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1280,720")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--remote-debugging-port=9222")

        # Disable Chrome UI elements and warning banners
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--disable-popup-blocking")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)

        # Suppress "Chrome is being controlled by automated test software" banner
        # and auto-deny permission popups
        prefs = {
            "profile.default_content_setting_values.notifications": 2,  # 2 = Block (1 = Allow, 2 = Block)
            "profile.default_content_setting_values.media_stream": 2,  # Block camera/mic
            "profile.default_content_setting_values.geolocation": 2,  # Block location
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
        }
        chrome_options.add_experimental_option("prefs", prefs)

        # Additional argument to suppress permission prompts
        chrome_options.add_argument("--deny-permission-prompts")

        print(
            "Initializing ChromeDriver in HEADED mode (visible in VNC)...", flush=True
        )

        # Initialize driver ONCE
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(5)

        # Window management - bring Chrome to front (like Playwright)
        print("Setting up window management...", flush=True)
        time.sleep(2)  # Let Chrome window appear

        # Minimize Activity Monitor
        os.system(
            "DISPLAY=:99 xdotool search --name 'Activity Monitor' windowminimize 2>/dev/null || true"
        )

        # Activate and raise Chrome window
        os.system(
            "DISPLAY=:99 xdotool search --class chrome windowactivate --sync windowraise 2>/dev/null || true"
        )

        # Make Chrome fullscreen
        os.system(
            "DISPLAY=:99 xdotool search --class chrome key F11 2>/dev/null || true"
        )

        print("Chrome window brought to front", flush=True)
        print("Selenium server ready", flush=True)

        # Keep server alive and process commands
        while True:
            try:
                # Check for command file
                try:
                    read_start = time.time()
                    with open("/tmp/selenium_command.json", "r") as f:
                        cmd = json.load(f)
                    read_elapsed = time.time() - read_start
                    print(f"⏱️  [Server] Command file read took: {read_elapsed:.3f}s", flush=True)
                except FileNotFoundError:
                    time.sleep(0.5)
                    continue

                # Remove command file immediately
                import os

                try:
                    rm_start = time.time()
                    os.remove("/tmp/selenium_command.json")
                    rm_elapsed = time.time() - rm_start
                    print(f"⏱️  [Server] Command file removal took: {rm_elapsed:.3f}s", flush=True)
                except:
                    pass

                # Execute command
                command_start = time.time()
                result = {"success": True}
                action = cmd.get("action")

                print(f"🔧 [Server] Executing: {action}", flush=True)

                if action == "navigate":
                    nav_start = time.time()
                    driver.get(cmd["url"])
                    nav_elapsed = time.time() - nav_start
                    print(f"⏱️  [Server] driver.get() took: {nav_elapsed:.3f}s", flush=True)
                    
                    sleep_start = time.time()
                    time.sleep(2)  # Wait for page to load
                    sleep_elapsed = time.time() - sleep_start
                    print(f"⏱️  [Server] sleep(2) took: {sleep_elapsed:.3f}s", flush=True)

                    # Ensure Chrome stays on top after navigation
                    window_start = time.time()
                    os.system(
                        "DISPLAY=:99 xdotool search --name 'Activity Monitor' windowminimize 2>/dev/null || true"
                    )
                    os.system(
                        "DISPLAY=:99 xdotool search --class chrome windowactivate windowraise 2>/dev/null || true"
                    )
                    window_elapsed = time.time() - window_start
                    print(f"⏱️  [Server] Window management took: {window_elapsed:.3f}s", flush=True)

                    # Extract page info
                    extract_start = time.time()
                    result["url"] = driver.current_url
                    result["title"] = driver.title

                    # Find ALL elements (interactive + content) - like Playwright
                    elements = []

                    # 1. Get interactive elements first
                    for tag in ["a", "button", "input", "select", "textarea"]:
                        for elem in driver.find_elements(By.TAG_NAME, tag):
                            if elem.is_displayed():
                                try:
                                    elements.append(
                                        {
                                            "tag": tag,
                                            "type": elem.get_attribute("type")
                                            or "interactive",
                                            "text": (
                                                elem.text[:100] if elem.text else ""
                                            ),
                                            "id": elem.get_attribute("id") or "",
                                            "name": elem.get_attribute("name") or "",
                                            "class": elem.get_attribute("class") or "",
                                        }
                                    )
                                except:
                                    pass

                    # 2. Get content elements (headings, important divs, etc.)
                    for tag in ["h1", "h2", "h3", "h4", "h5", "h6", "img"]:
                        for elem in driver.find_elements(By.TAG_NAME, tag):
                            if elem.is_displayed():
                                try:
                                    text = (
                                        elem.text[:100]
                                        if elem.text
                                        else elem.get_attribute("alt") or ""
                                    )
                                    if text or tag == "img":
                                        elements.append(
                                            {
                                                "tag": tag,
                                                "type": "content",
                                                "text": text,
                                                "id": elem.get_attribute("id") or "",
                                                "class": elem.get_attribute("class")
                                                or "",
                                                "src": elem.get_attribute("src") or "",
                                            }
                                        )
                                except:
                                    pass

                    # 3. Get loading/error indicators
                    for class_pattern in ["loading", "spinner", "error", "alert"]:
                        for elem in driver.find_elements(
                            By.CSS_SELECTOR, f"[class*='{class_pattern}']"
                        ):
                            if elem.is_displayed():
                                try:
                                    elements.append(
                                        {
                                            "tag": elem.tag_name,
                                            "type": "content",
                                            "text": elem.text[:50] if elem.text else "",
                                            "class": elem.get_attribute("class") or "",
                                        }
                                    )
                                except:
                                    pass

                    result["elements"] = elements
                    result["element_count"] = len(elements)
                    result["page_text"] = driver.find_element(By.TAG_NAME, "body").text[
                        :1000
                    ]
                    
                    extract_elapsed = time.time() - extract_start
                    print(f"⏱️  [Server] Element extraction took: {extract_elapsed:.3f}s ({len(elements)} elements)", flush=True)

                elif action == "click":
                    selector = cmd["selector"]

                    try:
                        if selector.startswith("//"):
                            # XPath
                            element = WebDriverWait(driver, 10).until(
                                EC.element_to_be_clickable((By.XPATH, selector))
                            )
                        else:
                            # CSS selector
                            element = WebDriverWait(driver, 10).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                            )
                        element.click()
                        time.sleep(2)  # Wait for any page changes

                        # Keep window on top
                        os.system(
                            "DISPLAY=:99 xdotool search --name 'Activity Monitor' windowminimize 2>/dev/null || true"
                        )
                        os.system(
                            "DISPLAY=:99 xdotool search --class chrome windowactivate windowraise 2>/dev/null || true"
                        )

                        result["url"] = driver.current_url
                        result["title"] = driver.title
                        result["message"] = f"Clicked: {selector}"

                        # Extract elements after click - with error handling for closed modals/popups
                        elements = []
                        extraction_failed = False

                        try:
                            for tag in ["a", "button", "input", "select", "textarea"]:
                                for elem in driver.find_elements(By.TAG_NAME, tag):
                                    try:
                                        if elem.is_displayed():
                                            elements.append(
                                                {
                                                    "tag": tag,
                                                    "type": elem.get_attribute("type")
                                                    or "interactive",
                                                    "text": (
                                                        elem.text[:100]
                                                        if elem.text
                                                        else ""
                                                    ),
                                                    "id": elem.get_attribute("id")
                                                    or "",
                                                    "name": elem.get_attribute("name")
                                                    or "",
                                                    "class": elem.get_attribute("class")
                                                    or "",
                                                }
                                            )
                                    except:
                                        # Element became stale (modal closed, etc) - skip it
                                        pass
                        except Exception as e:
                            # Page changed drastically (popup closed, navigation, etc)
                            extraction_failed = True
                            result["note"] = (
                                "Click successful but element extraction failed (page changed significantly)"
                            )

                        result["elements"] = elements
                        result["element_count"] = len(elements)

                        # If extraction totally failed, at least say click was successful
                        if extraction_failed and len(elements) == 0:
                            result["note"] = (
                                "Click successful. Page changed (popup closed or navigation occurred)."
                            )

                    except Exception as e:
                        result["success"] = False
                        result["error"] = f"Click failed for selector '{selector}'"
                        result["error_type"] = type(e).__name__
                        result["error_details"] = str(e)
                        result["current_url"] = driver.current_url
                        result["available_elements"] = (
                            f"{len(driver.find_elements(By.TAG_NAME, 'button'))} buttons, {len(driver.find_elements(By.TAG_NAME, 'a'))} links"
                        )

                        # Try to provide helpful suggestions
                        if "no such element" in str(e).lower():
                            result["suggestion"] = (
                                f"Element with selector '{selector}' not found. Try a different selector or wait for page to load."
                            )
                        elif "not clickable" in str(e).lower():
                            result["suggestion"] = (
                                f"Element '{selector}' found but not clickable. It might be hidden or covered."
                            )
                        elif "timeout" in str(e).lower():
                            result["suggestion"] = (
                                f"Timeout waiting for element '{selector}'. Page might still be loading."
                            )

                elif action == "input_text":
                    selector = cmd["selector"]
                    text = cmd["text"]

                    try:
                        if selector.startswith("//"):
                            element = driver.find_element(By.XPATH, selector)
                        else:
                            element = driver.find_element(By.CSS_SELECTOR, selector)

                        element.clear()
                        element.send_keys(text)

                        result["message"] = f"Filled field: {selector}"

                    except Exception as e:
                        result["success"] = False
                        result["error"] = f"Input failed for selector '{selector}'"
                        result["error_type"] = type(e).__name__
                        result["error_details"] = str(e)
                        result["text_attempted"] = text[:50] if text else ""

                        if "no such element" in str(e).lower():
                            result["suggestion"] = (
                                f"Input field '{selector}' not found. Check selector or wait for page load."
                            )
                        elif "element not interactable" in str(e).lower():
                            result["suggestion"] = (
                                f"Input field '{selector}' found but not interactable. It might be disabled or hidden."
                            )

                elif action == "get_page_info":
                    result["title"] = driver.title
                    result["url"] = driver.current_url
                    result["page_text"] = driver.find_element(By.TAG_NAME, "body").text[
                        :2000
                    ]

                elif action == "take_screenshot":
                    file_path = cmd.get("file_path", "screenshot.png")
                    driver.save_screenshot(f"/home/user/{file_path}")
                    result["file_path"] = file_path
                    result["message"] = f"Screenshot saved to {file_path}"

                elif action == "go_back":
                    driver.back()
                    time.sleep(1)
                    result["url"] = driver.current_url

                elif action == "go_forward":
                    driver.forward()
                    time.sleep(1)
                    result["url"] = driver.current_url

                elif action == "refresh":
                    driver.refresh()
                    time.sleep(1)

                elif action == "wait":
                    seconds = cmd.get("seconds", 5)
                    time.sleep(seconds)
                    result["message"] = f"Waited {seconds} seconds"

                else:
                    result["success"] = False
                    result["error"] = f"Unknown action: {action}"

                # Log command execution time
                command_elapsed = time.time() - command_start
                print(f"⏱️  [Server] Command execution took: {command_elapsed:.3f}s", flush=True)

                # Write response
                write_start = time.time()
                with open("/tmp/selenium_response.json", "w") as f:
                    json.dump(result, f)
                write_elapsed = time.time() - write_start
                print(f"⏱️  [Server] Response write took: {write_elapsed:.3f}s", flush=True)

                total_elapsed = time.time() - command_start
                print(f"✅ [Server] Completed: {action} (total: {total_elapsed:.3f}s)", flush=True)

            except Exception as e:
                # Write error response
                error_result = {
                    "success": False,
                    "error": f"{type(e).__name__}: {str(e)}",
                    "traceback": traceback.format_exc(),
                }
                try:
                    with open("/tmp/selenium_response.json", "w") as f:
                        json.dump(error_result, f)
                except:
                    pass
                print(f"Error: {e}", flush=True)

    except Exception as e:
        print(f"Fatal error: {e}", flush=True)
        traceback.print_exc()

    finally:
        if driver:
            driver.quit()
            print("Selenium server shutting down", flush=True)


if __name__ == "__main__":
    main()