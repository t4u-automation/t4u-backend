"""E2B Web Search Tool - Google Custom Search running in E2B sandbox"""

from typing import Optional

from app.e2b.tool_base import E2BToolsBase
from app.tool.base import ToolResult
from app.utils.logger import logger

_WEB_SEARCH_DESCRIPTION = """\
Search the web using Google Custom Search API.
Runs inside E2B sandbox with full internet access.

Perfect for:
- Finding URLs, documentation, articles
- Discovering resources and information
- Getting quick answers to questions

Returns URLs, titles, and descriptions of search results.
"""


class E2BWebSearchTool(E2BToolsBase):
    """
    Web search tool using Google Custom Search API in E2B sandbox.
    Provides fast, reliable search results from Google.
    """

    name: str = "e2b_web_search"
    description: str = _WEB_SEARCH_DESCRIPTION
    parameters: dict = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query string",
            },
            "num_results": {
                "type": "integer",
                "description": "Number of results to return (default: 5, max: 10)",
                "default": 5,
            },
        },
        "required": ["query"],
    }

    async def execute(self, query: str, num_results: int = 5, **kwargs) -> ToolResult:
        """
        Execute Google Custom Search in E2B sandbox

        Args:
            query: Search query string
            num_results: Number of results to return (1-10)
        """
        if not self.sandbox:
            return self.fail_response("E2B sandbox not initialized")

        try:
            # Get API keys from config (passed as env vars or read from config)
            from app.config import config

            if (
                not config.search_config
                or not config.search_config.google_api_key
                or not config.search_config.google_search_engine_id
            ):
                return self.fail_response(
                    "Google Custom Search API not configured. Set google_api_key and google_search_engine_id in config.toml"
                )

            google_api_key = config.search_config.google_api_key
            search_engine_id = config.search_config.google_search_engine_id

            # Limit num_results
            num_results = max(1, min(num_results, 10))

            # Create search script using the existing google_search.py implementation
            search_script = f"""
import json
import sys

# Ensure requests is available
try:
    import requests
except ImportError:
    import subprocess
    print("Installing requests...", file=sys.stderr, flush=True)
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "requests"])
    import requests

def google_search(query, api_key, search_engine_id, num_results=10):
    \"\"\"
    Google Custom Search API implementation.
    Based on app/tool/search/google_search.py
    \"\"\"
    try:
        # Call Google Custom Search API
        url = "https://www.googleapis.com/customsearch/v1"
        params = {{
            "key": api_key,
            "cx": search_engine_id,
            "q": query,
            "num": min(num_results, 10),  # API max is 10 per request
        }}

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()

        # Parse results
        results = []
        if "items" in data:
            for item in data["items"]:
                results.append({{
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "description": item.get("snippet", ""),
                }})

        return {{"success": True, "results": results}}

    except requests.exceptions.HTTPError as e:
        return {{"success": False, "error": f"HTTP error: {{e.response.status_code}} - {{e.response.text}}"}}
    except requests.exceptions.RequestException as e:
        return {{"success": False, "error": f"Request failed: {{str(e)}}"}}
    except Exception as e:
        return {{"success": False, "error": f"Unexpected error: {{str(e)}}"}}

# Execute search
result = google_search(
    query={repr(query)},
    api_key={repr(google_api_key)},
    search_engine_id={repr(search_engine_id)},
    num_results={num_results}
)

print(json.dumps(result))
"""

            # Write and execute search script
            import time

            timestamp = int(time.time() * 1000)
            script_path = f"/tmp/web_search_{timestamp}.py"

            logger.info(f"🔎 Executing Google search for: {query}")
            self.sandbox.filesystem_write(script_path, search_script)

            result = self.sandbox.exec(f"python3 {script_path}", timeout=15)

            # Cleanup
            try:
                self.sandbox.exec(f"rm -f {script_path}")
            except:
                pass

            if result.exit_code != 0:
                error_msg = f"Search failed: {result.stderr or result.stdout}"
                logger.error(error_msg)
                return self.fail_response(error_msg)

            # Parse results
            import json

            try:
                search_result = json.loads(result.stdout.strip())
            except Exception as e:
                logger.error(f"Failed to parse search results: {e}")
                return self.fail_response(f"Failed to parse results: {e}")

            if not search_result.get("success"):
                error = search_result.get("error", "Unknown error")
                logger.error(f"Google search error: {error}")
                return self.fail_response(f"Search error: {error}")

            results = search_result.get("results", [])

            if not results:
                return self.success_response(f"No results found for '{query}'")

            # Format response
            response_parts = [f"Search results for '{query}':\n"]

            for i, item in enumerate(results, 1):
                response_parts.append(f"{i}. {item['title']}")
                response_parts.append(f"   URL: {item['url']}")
                response_parts.append(f"   Description: {item['description']}")
                response_parts.append("")

            return self.success_response("\n".join(response_parts))

        except Exception as e:
            logger.error(f"E2B web search error: {e}")
            import traceback

            traceback.print_exc()
            return self.fail_response(f"Web search execution error: {e}")
