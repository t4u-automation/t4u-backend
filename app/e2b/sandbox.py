"""E2B Sandbox management for TestOpsAI"""

import logging
from typing import Any, Dict, Optional

from e2b import Sandbox

from app.config import config
from app.utils.logger import logger

# Suppress verbose E2B logs
logging.getLogger("e2b").setLevel(logging.ERROR)


# E2B settings and global sandbox instance
e2b_settings = config.e2b
e2b_client = None


class E2BSandbox:
    """
    Wrapper class for E2B Sandbox with additional functionality.
    Provides a unified interface similar to Daytona sandbox.
    """

    def __init__(self, sandbox: Sandbox):
        self.sandbox = sandbox
        self.id = sandbox.sandbox_id  # E2B uses sandbox_id, not id
        self.vnc_host = None

    def get_vnc_host(self) -> str:
        """Get the public VNC host URL"""
        if not self.vnc_host:
            self.vnc_host = self.sandbox.get_host(5900)
        return self.vnc_host

    def exec(self, command: str, timeout: int = 30) -> Any:
        """
        Execute a command in the sandbox.

        Args:
            command: Command to execute
            timeout: Command timeout in seconds

        Returns:
            Command result with stdout, stderr, and exit_code
        """
        try:
            result = self.sandbox.commands.run(command, timeout=timeout)

            # Convert E2B result to a compatible format
            class CommandResult:
                def __init__(self, e2b_result):
                    self.stdout = e2b_result.stdout
                    self.stderr = e2b_result.stderr
                    self.exit_code = e2b_result.exit_code
                    self.result = (
                        e2b_result.stdout
                        if e2b_result.exit_code == 0
                        else e2b_result.stderr
                    )

            return CommandResult(result)

        except Exception as e:
            pass  # Silent error handling

            # Return error result
            class ErrorResult:
                def __init__(self, error_msg):
                    self.stdout = ""
                    self.stderr = str(error_msg)
                    self.exit_code = 1
                    self.result = str(error_msg)

            return ErrorResult(e)

    def filesystem_write(self, path: str, content: str) -> bool:
        """
        Write content to a file in the sandbox.

        Args:
            path: File path in sandbox
            content: Content to write

        Returns:
            True if successful
        """
        try:
            self.sandbox.files.write(path, content)
            pass  # Silent success
            return True
        except Exception as e:
            pass
            return False

    def filesystem_read(self, path: str, binary: bool = False) -> Optional[str]:
        """
        Read content from a file in the sandbox.

        Args:
            path: File path in sandbox
            binary: Whether to read as binary (for images, etc.)

        Returns:
            File content or None if error
        """
        try:
            if binary:
                # For binary files, use base64 encoding through shell
                result = self.sandbox.commands.run(f"base64 {path}")
                if result.exit_code == 0:
                    import base64

                    return base64.b64decode(result.stdout.strip())
                else:
                    return None
            else:
                content = self.sandbox.files.read(path)
                return content
        except Exception as e:
            pass
            return None

    def filesystem_list(self, path: str = ".") -> list:
        """
        List files in a directory.

        Args:
            path: Directory path

        Returns:
            List of file/directory names
        """
        try:
            result = self.sandbox.commands.run(f"ls -la {path}")
            return result.stdout.split("\n")
        except Exception as e:
            pass
            return []

    def close(self):
        """Close/kill the sandbox"""
        try:
            if self.sandbox:
                self.sandbox.kill()  # E2B uses kill() not close()
                # Sandbox closed (logged to file only)
        except Exception as e:
            logger.error(f"Error closing E2B sandbox: {e}")


async def create_sandbox(
    template: Optional[str] = None,
    timeout: Optional[int] = None,
    cwd: Optional[str] = None,
    env_vars: Optional[Dict[str, str]] = None,
    metadata: Optional[Dict[str, str]] = None,
) -> E2BSandbox:
    """
    Create a new E2B sandbox with the specified configuration.

    Args:
        template: E2B template to use (defaults to config setting)
        timeout: Sandbox timeout in seconds (defaults to config setting)
        cwd: Working directory (defaults to config setting)
        env_vars: Environment variables to set
        metadata: Metadata for the sandbox

    Returns:
        E2BSandbox instance
    """
    if not e2b_settings:
        raise ValueError(
            "E2B configuration not found. Please set e2b_api_key in config.toml"
        )

    try:
        import time
        sandbox_start = time.time()
        
        logger.info("Creating new E2B sandbox environment")

        # Use config defaults if not provided
        template = template or e2b_settings.template
        timeout = timeout or e2b_settings.timeout
        cwd = cwd or e2b_settings.cwd

        # Create E2B sandbox (resources defined in template: 4 vCPUs, 4GB RAM)
        # E2B SDK is synchronous - run in thread pool to avoid blocking event loop
        import asyncio
        loop = asyncio.get_event_loop()
        
        sandbox = await loop.run_in_executor(
            None,  # Use default executor
            lambda: Sandbox.create(
                template=template,
                timeout=timeout,
                envs=env_vars or {},
                metadata=metadata or {},
                allow_internet_access=True,
                api_key=e2b_settings.e2b_api_key,
            )
        )
        
        sandbox_creation_time = time.time() - sandbox_start

        print(f"\n{'='*70}")
        print(f"🟢 SANDBOX PROVISIONED ({sandbox_creation_time:.2f}s)")
        print(f"{'='*70}")
        print(f"Sandbox ID: {sandbox.sandbox_id}")
        print(f"Template: {template}")

        # Wrap in our custom class
        e2b_sandbox = E2BSandbox(sandbox)

        # Check if using base template (needs installation) or custom template (pre-installed)
        if template == "base":
            # Installing dependencies (logged to file only)

            # Install only essential packages
            install_cmd = """
export DEBIAN_FRONTEND=noninteractive
apt-get update > /dev/null 2>&1
apt-get install -y tmux > /dev/null 2>&1
pip install playwright > /dev/null 2>&1
playwright install chromium > /dev/null 2>&1
playwright install-deps chromium > /dev/null 2>&1
echo "✅ Setup complete"
"""
            result = e2b_sandbox.exec(install_cmd, timeout=120)
            if result.exit_code != 0:
                logger.warning(f"⚠️  Installation issues: {result.stderr}")
        else:
            # Custom template - Playwright pre-installed
            pass

        # Start pre-installed desktop services (everything already installed in template)
        desktop_start = time.time()
        
        # Run the pre-installed startup script and verify services started
        # Start services in background and do quick verification (non-blocking)
        desktop_setup = """
#!/bin/bash
# Run startup script if it exists, otherwise start services manually
if [ -f /home/user/start_desktop.sh ]; then
    bash /home/user/start_desktop.sh > /tmp/startup.log 2>&1 &
    STARTUP_PID=$!
else
    # Fallback: start services manually
    export DISPLAY=:99
    nohup Xvfb :99 -screen 0 1280x720x24 > /tmp/xvfb.log 2>&1 &
    sleep 2
    nohup fluxbox > /tmp/fluxbox.log 2>&1 &
    sleep 1
    nohup x11vnc -display :99 -forever -shared -nopw -rfbport 5900 > /tmp/vnc.log 2>&1 &
    sleep 1
    cd /home/user/novnc && nohup websockify --web . --daemon 0.0.0.0:6080 localhost:5900 > /tmp/websockify.log 2>&1 &
fi

# Give services a moment to start (Firebase initialization can take a few seconds)
sleep 8

# Quick verification (non-blocking checks)
if pgrep -f websockify > /dev/null 2>&1; then
    echo "✅ Websockify process found"
    pgrep -a websockify | head -1
else
    echo "⚠️  Websockify process not found after 8s"
    echo "--- websockify.log (last 20 lines) ---"
    tail -20 /tmp/websockify.log 2>/dev/null || echo "No logs found"
    echo "---"
fi

# Check port (quick check, don't wait)
if netstat -tuln 2>/dev/null | grep -q 6080 || ss -tuln 2>/dev/null | grep -q 6080; then
    echo "✅ Port 6080 listening"
else
    echo "⚠️  Port 6080 not listening yet (may take a few more seconds)"
fi

echo "✅ Desktop services startup completed"
"""
        
        # Run desktop startup in thread pool (exec is synchronous)
        # Script should complete in ~10-15 seconds (starts services in background, waits 8s, then quick checks)
        result = await loop.run_in_executor(
            None,
            lambda: e2b_sandbox.exec(desktop_setup, timeout=30)
        )
        desktop_time = time.time() - desktop_start
        
        # Show VNC web access URL and desktop setup results
        vnc_web_host = e2b_sandbox.sandbox.get_host(6080)
        vnc_url = f"http://{vnc_web_host}/vnc.html"
        
        total_time = time.time() - sandbox_start
        
        print(f"VNC URL: {vnc_url}")
        print(f"Desktop setup: {desktop_time:.2f}s")
        print(f"Desktop output:")
        for line in result.stdout.split('\n')[-10:]:  # Last 10 lines
            if line.strip():
                print(f"  {line}")
        if result.stderr:
            print(f"Desktop errors: {result.stderr[:500]}")
        
        # Check websockify logs if process is running but port not listening
        if "✅ Websockify process found" in result.stdout and "Port 6080 not listening" in result.stdout:
            print(f"\n⚠️  Websockify process found but port not listening - waiting and checking again...")
            await asyncio.sleep(5)  # Wait a bit more for websockify to fully start
            
            # Check again
            check_result = await loop.run_in_executor(
                None,
                lambda: e2b_sandbox.exec("pgrep -a websockify && (netstat -tuln 2>&1 | grep 6080 || ss -tuln 2>&1 | grep 6080 || echo 'Port still not listening') || echo 'websockify crashed'", timeout=10)
            )
            print(f"Status after wait: {check_result.stdout}")
            
            # Get logs
            log_check = await loop.run_in_executor(
                None,
                lambda: e2b_sandbox.exec("tail -50 /tmp/websockify.log 2>&1 || echo 'No logs found'", timeout=5)
            )
            if log_check.stdout:
                print(f"\nWebsockify logs:\n{log_check.stdout[:800]}")
        
        print(f"Total ready time: {total_time:.2f}s")
        print(f"{'='*70}\n")

        return e2b_sandbox

    except Exception as e:
        logger.error(f"Error creating E2B sandbox: {e}")
        raise


def delete_sandbox(sandbox: E2BSandbox) -> bool:
    """
    Delete an E2B sandbox.

    Args:
        sandbox: E2BSandbox instance to delete

    Returns:
        True if successful
    """
    try:
        sandbox_id = sandbox.id
        sandbox.close()

        print(f"\n{'='*70}")
        print(f"🔴 SANDBOX DELETED")
        print(f"{'='*70}")
        print(f"Sandbox ID: {sandbox_id}")
        print(f"{'='*70}\n")
        
        return True

    except Exception as e:
        logger.error(f"Error deleting E2B sandbox: {e}")
        return False
