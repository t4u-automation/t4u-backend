"""E2B Crawl4AI Tool - Web crawler running in E2B sandbox with Playwright"""

import asyncio
import json
from typing import List, Optional, Union

from app.e2b.tool_base import E2BToolsBase
from app.tool.base import ToolResult
from app.utils.logger import logger

_CRAWL4AI_DESCRIPTION = """\
Web crawler that extracts clean, AI-ready content from web pages.
Runs inside E2B sandbox using pre-installed Playwright.

Features:
- Extracts clean markdown content optimized for LLMs
- Handles JavaScript-heavy sites and dynamic content
- Supports multiple URLs in a single request
- Fast and reliable with built-in error handling

Perfect for content analysis, research, and feeding web content to AI models.
"""


class E2BCrawl4AITool(E2BToolsBase):
    """
    Web crawler tool using Crawl4AI in E2B sandbox.
    Leverages E2B's pre-installed Playwright for fast, reliable crawling.
    """

    name: str = "e2b_crawl4ai"
    description: str = _CRAWL4AI_DESCRIPTION
    parameters: dict = {
        "type": "object",
        "properties": {
            "urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of URLs to crawl (or single URL string)",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds for each URL (default: 30)",
                "default": 30,
            },
            "word_count_threshold": {
                "type": "integer",
                "description": "Minimum word count for content blocks (default: 10)",
                "default": 10,
            },
        },
        "required": ["urls"],
    }

    async def execute(
        self,
        urls: Union[str, List[str]],
        timeout: int = 30,
        word_count_threshold: int = 10,
        **kwargs,
    ) -> ToolResult:
        """
        Execute web crawling for the specified URLs in E2B sandbox

        Args:
            urls: Single URL or list of URLs to crawl
            timeout: Timeout per URL in seconds
            word_count_threshold: Min words per content block
        """
        if not self.sandbox:
            return self.fail_response("E2B sandbox not initialized")

        try:
            # Normalize URLs to list
            if isinstance(urls, str):
                url_list = [urls]
            else:
                url_list = urls

            # Create crawler script that will run in E2B
            crawler_script = f"""
import asyncio
import json
import os
import shutil

async def crawl_urls():
    # Clear any Crawl4AI cache to prevent stale results
    cache_dir = os.path.expanduser("~/.crawl4ai")
    if os.path.exists(cache_dir):
        try:
            shutil.rmtree(cache_dir)
            print(f"Cleared cache directory: {{cache_dir}}", flush=True)
        except:
            pass

    # Try to import crawl4ai
    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
    except ImportError:
        # Install crawl4ai if not present
        import subprocess
        print("Installing crawl4ai...", flush=True)
        subprocess.check_call(["pip", "install", "-q", "crawl4ai"])
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

    # Configure browser
    browser_config = BrowserConfig(
        headless=True,
        verbose=False,
        browser_type="chromium",
    )

    # Configure crawler
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        word_count_threshold={word_count_threshold},
        process_iframes=True,
        remove_overlay_elements=True,
        page_timeout={timeout * 1000},
        wait_until="domcontentloaded",
    )

    results = []
    urls = {json.dumps(url_list)}

    async with AsyncWebCrawler(config=browser_config) as crawler:
        for url in urls:
            try:
                print(f"Crawling: {{url}}", flush=True)
                result = await crawler.arun(url=url, config=run_config)

                if result.success:
                    word_count = len(result.markdown.split()) if result.markdown else 0

                    results.append({{
                        "url": url,
                        "success": True,
                        "title": result.metadata.get("title") if result.metadata else None,
                        "markdown": result.markdown[:50000] if result.markdown else None,  # Limit size
                        "word_count": word_count,
                    }})
                else:
                    results.append({{
                        "url": url,
                        "success": False,
                        "error": getattr(result, "error_message", "Unknown error"),
                    }})
            except Exception as e:
                results.append({{
                    "url": url,
                    "success": False,
                    "error": str(e),
                }})

    print(json.dumps(results), flush=True)

if __name__ == "__main__":
    asyncio.run(crawl_urls())
"""

            # Write crawler script to E2B with unique name to avoid caching
            import time

            timestamp = int(time.time() * 1000)
            script_path = f"/tmp/crawl4ai_runner_{timestamp}.py"
            logger.info(f"📝 Writing crawler script for URLs: {url_list}")
            self.sandbox.filesystem_write(script_path, crawler_script)

            # Run crawler script
            logger.info(f"🕷️ Running crawl4ai for {len(url_list)} URL(s)...")
            result = self.sandbox.exec(
                f"cd /home/user && python3 {script_path}",
                timeout=timeout * len(url_list) + 60,  # Extra time for overhead
            )

            logger.info(f"Crawl4AI execution completed: exit_code={result.exit_code}")

            # Cleanup: Remove the script file to prevent any caching issues
            try:
                self.sandbox.exec(f"rm -f {script_path}")
            except:
                pass

            if result.exit_code != 0:
                error_msg = f"Crawl4AI failed: {result.stderr or result.stdout}"
                logger.error(error_msg)
                return self.fail_response(error_msg)

            # Parse results
            try:
                # Extract JSON from output (last line should be JSON)
                output_lines = result.stdout.strip().split("\n")
                json_output = output_lines[-1]  # Last line is the JSON results
                crawl_results = json.loads(json_output)
            except Exception as e:
                logger.error(f"Failed to parse crawl results: {e}")
                logger.error(f"Output was: {result.stdout[:500]}")
                return self.fail_response(f"Failed to parse results: {e}")

            # Format response
            response_parts = []
            successful = sum(1 for r in crawl_results if r.get("success"))
            failed = len(crawl_results) - successful

            response_parts.append(
                f"Crawled {len(crawl_results)} URL(s): {successful} successful, {failed} failed"
            )
            response_parts.append("")

            for i, result_item in enumerate(crawl_results, 1):
                url = result_item.get("url")

                if result_item.get("success"):
                    title = result_item.get("title", "No title")
                    word_count = result_item.get("word_count", 0)
                    markdown = result_item.get("markdown", "")

                    response_parts.append(f"{i}. {url}")
                    response_parts.append(f"   Title: {title}")
                    response_parts.append(f"   Words: {word_count}")
                    response_parts.append(f"   Content: {markdown[:500]}...")  # Preview
                    response_parts.append("")
                else:
                    error = result_item.get("error", "Unknown error")
                    response_parts.append(f"{i}. {url}")
                    response_parts.append(f"   ❌ Failed: {error}")
                    response_parts.append("")

            return self.success_response("\n".join(response_parts))

        except Exception as e:
            logger.error(f"E2B Crawl4AI error: {e}")
            import traceback

            traceback.print_exc()
            return self.fail_response(f"Crawl4AI execution error: {e}")
