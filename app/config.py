import json
import threading
import tomllib
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


def get_project_root() -> Path:
    """Get the project root directory"""
    return Path(__file__).resolve().parent.parent


PROJECT_ROOT = get_project_root()
WORKSPACE_ROOT = PROJECT_ROOT / "workspace"


class LLMPricing(BaseModel):
    """Pricing configuration for LLM models with tiered pricing"""

    input_price_low: float = Field(
        3.0, description="Price per million tokens for input ≤200K tokens"
    )
    input_price_high: float = Field(
        6.0, description="Price per million tokens for input >200K tokens"
    )
    output_price_low: float = Field(
        15.0, description="Price per million tokens for output ≤200K tokens"
    )
    output_price_high: float = Field(
        22.5, description="Price per million tokens for output >200K tokens"
    )
    tier_threshold: int = Field(200000, description="Token threshold for pricing tiers")


class LLMSettings(BaseModel):
    model: str = Field(..., description="Model name")
    base_url: str = Field(..., description="API base URL")
    api_key: str = Field(..., description="API key")
    max_tokens: int = Field(4096, description="Maximum number of tokens per request")
    max_input_tokens: Optional[int] = Field(
        None,
        description="Maximum input tokens to use across all requests (None for unlimited)",
    )
    temperature: float = Field(1.0, description="Sampling temperature")
    api_type: str = Field(..., description="Azure, Openai, or Ollama")
    api_version: str = Field(..., description="Azure Openai version if AzureOpenai")
    pricing: Optional[LLMPricing] = Field(
        None, description="Pricing configuration for cost tracking"
    )


class ProxySettings(BaseModel):
    server: str = Field(None, description="Proxy server address")
    username: Optional[str] = Field(None, description="Proxy username")
    password: Optional[str] = Field(None, description="Proxy password")


class SearchSettings(BaseModel):
    engine: str = Field(default="Google", description="Search engine the llm to use")
    fallback_engines: List[str] = Field(
        default_factory=lambda: ["DuckDuckGo", "Baidu", "Bing"],
        description="Fallback search engines to try if the primary engine fails",
    )
    retry_delay: int = Field(
        default=60,
        description="Seconds to wait before retrying all engines again after they all fail",
    )
    max_retries: int = Field(
        default=3,
        description="Maximum number of times to retry all engines when all fail",
    )
    lang: str = Field(
        default="en",
        description="Language code for search results (e.g., en, zh, fr)",
    )
    country: str = Field(
        default="us",
        description="Country code for search results (e.g., us, cn, uk)",
    )
    google_api_key: Optional[str] = Field(
        default=None,
        description="Google Custom Search API key (https://console.cloud.google.com/apis/credentials)",
    )
    google_search_engine_id: Optional[str] = Field(
        default=None,
        description="Google Custom Search Engine ID / CX (https://programmablesearchengine.google.com/)",
    )


class RunflowSettings(BaseModel):
    use_data_analysis_agent: bool = Field(
        default=False, description="Enable data analysis agent in run flow"
    )


class BrowserSettings(BaseModel):
    headless: bool = Field(False, description="Whether to run browser in headless mode")
    disable_security: bool = Field(
        True, description="Disable browser security features"
    )
    extra_chromium_args: List[str] = Field(
        default_factory=list, description="Extra arguments to pass to the browser"
    )
    chrome_instance_path: Optional[str] = Field(
        None, description="Path to a Chrome instance to use"
    )
    wss_url: Optional[str] = Field(
        None, description="Connect to a browser instance via WebSocket"
    )
    cdp_url: Optional[str] = Field(
        None, description="Connect to a browser instance via CDP"
    )
    proxy: Optional[ProxySettings] = Field(
        None, description="Proxy settings for the browser"
    )
    max_content_length: int = Field(
        2000, description="Maximum length for content retrieval operations"
    )


class SandboxSettings(BaseModel):
    """Configuration for the execution sandbox"""

    use_sandbox: bool = Field(False, description="Whether to use the sandbox")
    image: str = Field("python:3.12-slim", description="Base image")
    work_dir: str = Field("/workspace", description="Container working directory")
    memory_limit: str = Field("512m", description="Memory limit")
    cpu_limit: float = Field(1.0, description="CPU limit")
    timeout: int = Field(300, description="Default command timeout (seconds)")
    network_enabled: bool = Field(
        False, description="Whether network access is allowed"
    )


class DaytonaSettings(BaseModel):
    daytona_api_key: str
    daytona_server_url: Optional[str] = Field(
        "https://app.daytona.io/api", description=""
    )
    daytona_target: Optional[str] = Field("us", description="enum ['eu', 'us']")
    sandbox_image_name: Optional[str] = Field("whitezxj/sandbox:0.1.0", description="")
    sandbox_entrypoint: Optional[str] = Field(
        "/usr/bin/supervisord -n -c /etc/supervisor/conf.d/supervisord.conf",
        description="",
    )
    # sandbox_id: Optional[str] = Field(
    #     None, description="ID of the daytona sandbox to use, if any"
    # )
    VNC_password: Optional[str] = Field(
        "123456", description="VNC password for the vnc service in sandbox"
    )


class E2BSettings(BaseModel):
    """Configuration for E2B sandbox environment"""

    e2b_api_key: str = Field(..., description="E2B API key from https://e2b.dev/docs")
    template: Optional[str] = Field(
        "base", description="E2B template to use: 'base', 'node', 'python', etc."
    )
    timeout: Optional[int] = Field(
        300, description="Default timeout for sandbox operations in seconds"
    )
    cwd: Optional[str] = Field(
        "/home/user", description="Working directory in the sandbox"
    )


class MCPServerConfig(BaseModel):
    """Configuration for a single MCP server"""

    type: str = Field(..., description="Server connection type (sse or stdio)")
    url: Optional[str] = Field(None, description="Server URL for SSE connections")
    command: Optional[str] = Field(None, description="Command for stdio connections")
    args: List[str] = Field(
        default_factory=list, description="Arguments for stdio command"
    )


class WebhookSettings(BaseModel):
    """Configuration for webhook integration"""

    enabled: bool = Field(default=False, description="Enable webhook integration")
    endpoint: str = Field(..., description="Webhook endpoint URL")
    api_key: str = Field(..., description="API key for webhook authentication")


class FirestoreSettings(BaseModel):
    """Configuration for Firestore integration"""

    enabled: bool = Field(default=False, description="Enable Firestore integration")
    service_account_path: str = Field(
        ..., description="Path to Firebase service account JSON file"
    )
    collection: str = Field(
        default="agent_steps", description="Firestore collection name"
    )
    storage_bucket: Optional[str] = Field(
        None,
        description="Firebase Storage bucket name (e.g., 'your-project.appspot.com')",
    )


class MCPSettings(BaseModel):
    """Configuration for MCP (Model Context Protocol)"""

    server_reference: str = Field(
        "app.mcp.server", description="Module reference for the MCP server"
    )
    servers: Dict[str, MCPServerConfig] = Field(
        default_factory=dict, description="MCP server configurations"
    )

    @classmethod
    def load_server_config(cls) -> Dict[str, MCPServerConfig]:
        """Load MCP server configuration from JSON file"""
        config_path = PROJECT_ROOT / "config" / "mcp.json"

        try:
            config_file = config_path if config_path.exists() else None
            if not config_file:
                return {}

            with config_file.open() as f:
                data = json.load(f)
                servers = {}

                for server_id, server_config in data.get("mcpServers", {}).items():
                    servers[server_id] = MCPServerConfig(
                        type=server_config["type"],
                        url=server_config.get("url"),
                        command=server_config.get("command"),
                        args=server_config.get("args", []),
                    )
                return servers
        except Exception as e:
            raise ValueError(f"Failed to load MCP server config: {e}")


class AppConfig(BaseModel):
    llm: Dict[str, LLMSettings]
    sandbox: Optional[SandboxSettings] = Field(
        None, description="Sandbox configuration"
    )
    browser_config: Optional[BrowserSettings] = Field(
        None, description="Browser configuration"
    )
    search_config: Optional[SearchSettings] = Field(
        None, description="Search configuration"
    )
    mcp_config: Optional[MCPSettings] = Field(None, description="MCP configuration")
    run_flow_config: Optional[RunflowSettings] = Field(
        None, description="Run flow configuration"
    )
    daytona_config: Optional[DaytonaSettings] = Field(
        None, description="Daytona configuration"
    )
    e2b_config: Optional[E2BSettings] = Field(None, description="E2B configuration")
    webhook_config: Optional[WebhookSettings] = Field(
        None, description="Webhook configuration"
    )
    firestore_config: Optional[FirestoreSettings] = Field(
        None, description="Firestore configuration"
    )

    class Config:
        arbitrary_types_allowed = True


class Config:
    _instance = None
    _lock = threading.Lock()
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            with self._lock:
                if not self._initialized:
                    self._config = None
                    self._load_initial_config()
                    self._initialized = True

    @staticmethod
    def _get_config_path() -> Path:
        root = PROJECT_ROOT
        config_path = root / "config" / "config.toml"
        if config_path.exists():
            return config_path
        example_path = root / "config" / "config.example.toml"
        if example_path.exists():
            return example_path
        raise FileNotFoundError("No configuration file found in config directory")

    def _load_config(self) -> dict:
        config_path = self._get_config_path()
        with config_path.open("rb") as f:
            return tomllib.load(f)

    def _load_initial_config(self):
        raw_config = self._load_config()
        base_llm = raw_config.get("llm", {})
        # Extract llm overrides (like llm.vision) but NOT pricing
        llm_overrides = {
            k: v
            for k, v in raw_config.get("llm", {}).items()
            if isinstance(v, dict) and k != "pricing"
        }

        default_settings = {
            "model": base_llm.get("model"),
            "base_url": base_llm.get("base_url"),
            "api_key": base_llm.get("api_key"),
            "max_tokens": base_llm.get("max_tokens", 4096),
            "max_input_tokens": base_llm.get("max_input_tokens"),
            "temperature": base_llm.get("temperature", 1.0),
            "api_type": base_llm.get("api_type", ""),
            "api_version": base_llm.get("api_version", ""),
            "pricing": (
                LLMPricing(**base_llm["pricing"]) if "pricing" in base_llm else None
            ),
        }

        # handle browser config.
        browser_config = raw_config.get("browser", {})
        browser_settings = None

        if browser_config:
            # handle proxy settings.
            proxy_config = browser_config.get("proxy", {})
            proxy_settings = None

            if proxy_config and proxy_config.get("server"):
                proxy_settings = ProxySettings(
                    **{
                        k: v
                        for k, v in proxy_config.items()
                        if k in ["server", "username", "password"] and v
                    }
                )

            # filter valid browser config parameters.
            valid_browser_params = {
                k: v
                for k, v in browser_config.items()
                if k in BrowserSettings.__annotations__ and v is not None
            }

            # if there is proxy settings, add it to the parameters.
            if proxy_settings:
                valid_browser_params["proxy"] = proxy_settings

            # only create BrowserSettings when there are valid parameters.
            if valid_browser_params:
                browser_settings = BrowserSettings(**valid_browser_params)

        search_config = raw_config.get("search", {})
        search_settings = None
        if search_config:
            search_settings = SearchSettings(**search_config)
        sandbox_config = raw_config.get("sandbox", {})
        if sandbox_config:
            sandbox_settings = SandboxSettings(**sandbox_config)
        else:
            sandbox_settings = SandboxSettings()
        daytona_config = raw_config.get("daytona", {})
        daytona_settings = None
        if daytona_config:
            daytona_settings = DaytonaSettings(**daytona_config)

        e2b_config = raw_config.get("e2b", {})
        e2b_settings = None
        if e2b_config:
            e2b_settings = E2BSettings(**e2b_config)

        webhook_config = raw_config.get("webhook", {})
        webhook_settings = None
        if webhook_config:
            webhook_settings = WebhookSettings(**webhook_config)

        firestore_config = raw_config.get("firestore", {})
        firestore_settings = None
        if firestore_config:
            firestore_settings = FirestoreSettings(**firestore_config)

        mcp_config = raw_config.get("mcp", {})
        mcp_settings = None
        if mcp_config:
            # Load server configurations from JSON
            mcp_config["servers"] = MCPSettings.load_server_config()
            mcp_settings = MCPSettings(**mcp_config)
        else:
            mcp_settings = MCPSettings(servers=MCPSettings.load_server_config())

        run_flow_config = raw_config.get("runflow")
        if run_flow_config:
            run_flow_settings = RunflowSettings(**run_flow_config)
        else:
            run_flow_settings = RunflowSettings()
        config_dict = {
            "llm": {
                "default": default_settings,
                **{
                    name: {**default_settings, **override_config}
                    for name, override_config in llm_overrides.items()
                },
            },
            "sandbox": sandbox_settings,
            "browser_config": browser_settings,
            "search_config": search_settings,
            "mcp_config": mcp_settings,
            "run_flow_config": run_flow_settings,
            "daytona_config": daytona_settings,
            "e2b_config": e2b_settings,
            "webhook_config": webhook_settings,
            "firestore_config": firestore_settings,
        }

        self._config = AppConfig(**config_dict)

    @property
    def llm(self) -> Dict[str, LLMSettings]:
        return self._config.llm

    @property
    def sandbox(self) -> SandboxSettings:
        return self._config.sandbox

    @property
    def daytona(self) -> DaytonaSettings:
        return self._config.daytona_config

    @property
    def browser_config(self) -> Optional[BrowserSettings]:
        return self._config.browser_config

    @property
    def search_config(self) -> Optional[SearchSettings]:
        return self._config.search_config

    @property
    def mcp_config(self) -> MCPSettings:
        """Get the MCP configuration"""
        return self._config.mcp_config

    @property
    def run_flow_config(self) -> RunflowSettings:
        """Get the Run Flow configuration"""
        return self._config.run_flow_config

    @property
    def e2b(self) -> Optional[E2BSettings]:
        """Get the E2B configuration"""
        return self._config.e2b_config

    @property
    def webhook(self) -> Optional[WebhookSettings]:
        """Get the Webhook configuration"""
        return self._config.webhook_config

    @property
    def firestore(self) -> Optional[FirestoreSettings]:
        """Get the Firestore configuration"""
        return self._config.firestore_config

    @property
    def workspace_root(self) -> Path:
        """Get the workspace root directory"""
        return WORKSPACE_ROOT

    @property
    def root_path(self) -> Path:
        """Get the root path of the application"""
        return PROJECT_ROOT


config = Config()
