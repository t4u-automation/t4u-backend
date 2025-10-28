# Contributing to T4U Backend

Thank you for your interest in contributing to the T4U (Test for You) AI-powered test automation platform!

## 🎯 Project Vision

T4U aims to democratize test automation by using AI agents that understand and execute web testing tasks like a human QA engineer would. Our focus is on:
- **Stable, reliable test automation** using semantic locators
- **AI-driven decision making** with minimal human intervention
- **Easy test creation** through natural language
- **Production-ready** test execution with validations

## 🚀 Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/t4u-backend.git
   cd t4u-backend
   ```
3. **Set up development environment:**
   ```bash
   python3.13 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
4. **Configure:**
   - Copy `config/config.example-model-anthropic.toml` to `config/config.toml`
   - Add your API keys (Anthropic, E2B, Firebase)
5. **Run locally:**
   ```bash
   python api_server.py
   ```

## 📋 Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/bug-description
```

### 2. Make Your Changes

Follow our coding standards (see below).

### 3. Test Your Changes

```bash
# Run the server
python api_server.py

# Test your feature manually
# Use Postman/curl to test API endpoints
```

### 4. Commit Your Changes

```bash
git add .
git commit -m "feat: add feature description"
```

**Commit Message Format:**
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `refactor:` Code refactoring
- `test:` Adding tests
- `chore:` Maintenance tasks

### 5. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub.

## 🎨 Coding Standards

### Python Style

- **PEP 8** compliance
- **Type hints** for function signatures
- **Docstrings** for classes and complex functions
- **async/await** for I/O operations

**Example:**
```python
async def execute_browser_action(
    self,
    action: str,
    by_text: Optional[str] = None,
    by_role: Optional[str] = None,
    **kwargs
) -> ToolResult:
    """
    Execute a browser action using stable Playwright locators.
    
    Args:
        action: Action type (click, fill, navigate_to)
        by_text: Locate element by visible text
        by_role: Locate element by ARIA role
        **kwargs: Additional action-specific parameters
        
    Returns:
        ToolResult with success status and output
    """
    # Implementation
```

### Locator Strategy

**ALWAYS use stable locators:**

```python
# ✅ Good - Stable across sessions
click(by_role='button', has_text='Submit')
fill(by_placeholder='Email', text='user@example.com')
fill(by_id='username', text='user')

# ❌ Bad - Breaks when page changes
click_element(index=0)
input_text(index=1, text='...')
```

### Error Handling

```python
try:
    result = await self._execute_browser_command(command)
    if not result.get("success"):
        return self.fail_response(result.get("error", "Action failed"))
    return self.success_response(result.get("message"))
except Exception as e:
    logger.error(f"Browser action failed: {e}")
    return self.fail_response(f"Error: {str(e)}")
```

### Logging

```python
from loguru import logger

# Use structured logging
logger.info("Browser action executed", action=action, duration=elapsed)
logger.error("Action failed", action=action, error=str(e))

# Use print for user-facing output
print(f"  ✅ Clicked button (2.3s)")
print(f"  ❌ Failed: Element not found")
```

## 🏗️ Architecture Guidelines

### Adding a New Tool

1. Create tool class inheriting from `BaseTool` or `E2BToolsBase`
2. Define parameters schema
3. Implement `async def execute()` method
4. Add to `ToolCollection`
5. Update prompts to include tool usage

**Example:**
```python
from app.tool.base import BaseTool
from app.schema import ToolResult

class MyNewTool(BaseTool):
    name: str = "my_tool"
    description: str = "Tool description"
    parameters: dict = {
        "type": "object",
        "properties": {
            "param1": {
                "type": "string",
                "description": "Parameter description"
            }
        },
        "required": ["param1"]
    }
    
    async def execute(self, param1: str, **kwargs) -> ToolResult:
        """Execute the tool"""
        try:
            # Implementation
            result = do_something(param1)
            return self.success_response(f"Success: {result}")
        except Exception as e:
            return self.fail_response(f"Error: {str(e)}")
```

### Adding Browser Actions

When adding new browser actions:
1. **Use stable locators** (by_role, by_text, by_id)
2. **Add to enum** in `e2b_browser_tool.py`
3. **Implement in browser script** (`persistent_browser.py`)
4. **Add to execute method**
5. **Update prompts** with usage examples
6. **Document** in README

## 🧪 Testing Guidelines

### Manual Testing

1. Start server: `python api_server.py`
2. Use API docs: `http://localhost:8000/docs`
3. Test endpoint with real scenario
4. Check VNC to see browser behavior
5. Verify Firestore updates

### Testing Checklist

- [ ] Action executes successfully
- [ ] Stable locators used (no indices)
- [ ] Error handling works
- [ ] Firestore updates correctly
- [ ] VNC shows expected behavior
- [ ] Proven steps can be replayed

## 📝 Documentation

### When to Update Docs

- **README.md** - New features, API changes
- **This file** - Process changes
- **Code comments** - Complex logic
- **Prompts** - Tool usage changes

### Documentation Style

- Clear, concise language
- Code examples for all features
- Explain WHY, not just HOW
- Include expected outputs

## 🐛 Reporting Issues

### Bug Reports

Include:
1. **Description** - What happened?
2. **Expected behavior** - What should happen?
3. **Steps to reproduce** - How to trigger the bug?
4. **Environment** - Python version, OS, dependencies
5. **Logs** - Relevant error messages
6. **VNC URL** - If browser-related

### Feature Requests

Include:
1. **Use case** - Why is this needed?
2. **Proposed solution** - How should it work?
3. **Alternatives** - Other approaches considered?

## 🤝 Pull Request Process

### Before Submitting

- [ ] Code follows style guidelines
- [ ] Uses stable locators (no indices)
- [ ] No secrets committed (API keys, service accounts)
- [ ] Tested locally
- [ ] Updated README if needed
- [ ] Meaningful commit messages

### PR Description Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
How was this tested?

## Checklist
- [ ] Code follows project style
- [ ] No secrets committed
- [ ] Tested locally
- [ ] Documentation updated
```

### Review Process

1. **Automated checks** - Code compiles, no secrets
2. **Maintainer review** - Code quality, architecture fit
3. **Testing** - Manual verification
4. **Merge** - Squash and merge to main

## 🔒 Security

### DO NOT Commit

- API keys (Anthropic, E2B, Google)
- Firebase service account JSON
- config/config.toml (has secrets)
- .env files
- Any credentials or tokens

### Use Example Files

- `config/config.example-model-anthropic.toml` ✅
- `.env.example` ✅
- Document what values are needed

## 💡 Tips for Contributors

### Understanding the Codebase

1. **Start with README.md** - Architecture overview
2. **Read run-logic.md** - Execution flow details
3. **Check api_server.py** - API endpoints
4. **Explore app/agent/** - Agent implementation
5. **Understand app/tool/e2b/e2b_browser_tool.py** - Core browser automation

### Key Concepts

**Stable Locators:**
- Always use `by_role`, `by_text`, `by_placeholder`, `by_id`
- Never use `index` for click/fill actions
- Indices break when page structure changes

**Sub-Agent Delegation:**
- Use for complex multi-step tasks
- Keeps main agent context clean
- Returns only summary, not detailed steps

**Assertions for Validation:**
- Use `assert_*` actions for verification
- Include `assertion_description` for clarity
- Assertions are saved in proven steps

### Common Patterns

**Browser Action Pattern:**
```python
# Discover elements
result = await browser.execute(action="get_by_role", role="button")

# Click using specific locator
result = await browser.execute(
    action="click",
    by_role="button",
    has_text="Submit"
)

# Validate outcome
result = await browser.execute(
    action="assert_url_contains",
    expected_text="/dashboard",
    assertion_description="Login successful"
)
```

## 📞 Questions?

- **GitHub Discussions** - General questions
- **GitHub Issues** - Bug reports, feature requests
- **Pull Requests** - Code contributions

## 🙏 Thank You!

Every contribution helps make AI-powered test automation more accessible!

---

**Happy coding!** 🚀

