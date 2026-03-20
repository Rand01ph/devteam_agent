# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

DevTeam Agent is a team work management agent built with Codex Agent SDK. It integrates with GitLab and Jira to automatically generate and manage weekly/monthly reports for team members.

## Development Commands

```bash
# Install dependencies
uv sync

# Run the agent
uv run python -m src.main

# Or directly
python -m src.main
```

## Architecture

The project uses the Codex Agent SDK to create an interactive conversational agent with MCP (Model Context Protocol) tools.

### Core Components

- **`src/main.py`**: `DevTeamAgent` class orchestrates the entire application. Initializes clients, creates MCP tools, and runs the conversation loop.

- **`src/config.py`**: Configuration dataclasses (`AgentConfig`, `GitLabConfig`, `JiraConfig`) loaded from environment variables.

- **`src/integrations/`**: API clients for external services
  - `gitlab_client.py`: Async HTTP client for GitLab API v4 (user events, issues, MRs)
  - `jira_client.py`: Async HTTP client for Jira REST API (issues, user activity)

- **`src/report/`**: Report management
  - `markdown_manager.py`: Parses and updates monthly Markdown files (format: `YYYY-MM.md`)
  - `generator.py`: Combines GitLab and Jira data to generate member weekly reports

- **`src/tools/`**: MCP tool definitions. Each module exports a `create_*_tools()` function that returns a list of tools decorated with `@tool` from `claude_agent_sdk`.

### Tool Pattern

Tools are created using the `@tool` decorator from `claude_agent_sdk`:

```python
from claude_agent_sdk import tool

@tool("tool_name", "description", {"param": type})
async def tool_name(args: dict[str, Any]):
    return {"content": [{"type": "text", "text": "result"}]}
```

Tools return MCP-formatted responses with `content` array containing text blocks.

### Report File Format

Monthly reports are stored in `data/reports/YYYY-MM.md` with structure:
- Top-level: `# 年月团队周报`
- Week sections: `# 第N周`
- Member sections: `## 成员名`

## Environment Configuration

Required environment variables (see `.env.example`):
- `GITLAB_URL`, `GITLAB_TOKEN`: GitLab instance and personal access token
- `JIRA_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN`: Jira credentials
- `TEAM_MEMBERS`: Comma-separated list of team member names
- Optional: `GITLAB_PROJECT_IDS`, `JIRA_PROJECT_KEYS` to filter specific projects
