"""Configuration management for DevTeam Agent."""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class GitLabConfig:
    """GitLab configuration."""
    url: str
    token: str
    project_ids: Optional[list[int]] = None  # Specific project IDs to track, None = all accessible

    @classmethod
    def from_env(cls) -> "GitLabConfig":
        """Load GitLab config from environment variables."""
        url = os.getenv("GITLAB_URL")
        token = os.getenv("GITLAB_TOKEN")

        if not url or not token:
            raise ValueError("GITLAB_URL and GITLAB_TOKEN must be set in environment variables")

        # Parse project IDs if provided (comma-separated)
        project_ids_str = os.getenv("GITLAB_PROJECT_IDS")
        project_ids = None
        if project_ids_str:
            project_ids = [int(pid.strip()) for pid in project_ids_str.split(",")]

        return cls(url=url, token=token, project_ids=project_ids)


@dataclass
class JiraConfig:
    """Jira configuration."""
    url: str
    username: str
    api_token: str
    project_keys: Optional[list[str]] = None  # Specific project keys to track, None = all accessible

    @classmethod
    def from_env(cls) -> "JiraConfig":
        """Load Jira config from environment variables."""
        url = os.getenv("JIRA_URL")
        username = os.getenv("JIRA_USERNAME")
        api_token = os.getenv("JIRA_API_TOKEN")

        if not url or not username or not api_token:
            raise ValueError("JIRA_URL, JIRA_USERNAME, and JIRA_API_TOKEN must be set in environment variables")

        # Parse project keys if provided (comma-separated)
        project_keys_str = os.getenv("JIRA_PROJECT_KEYS")
        project_keys = None
        if project_keys_str:
            project_keys = [key.strip() for key in project_keys_str.split(",")]

        return cls(url=url, username=username, api_token=api_token, project_keys=project_keys)


@dataclass
class ClaudeConfig:
    """Claude API configuration."""
    auth_token: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None

    @classmethod
    def from_env(cls) -> "ClaudeConfig":
        """Load Claude config from environment variables."""
        return cls(
            auth_token=os.getenv("ANTHROPIC_AUTH_TOKEN"),
            base_url=os.getenv("ANTHROPIC_BASE_URL"),
            model=os.getenv("ANTHROPIC_MODEL")
        )

    def to_env_dict(self) -> dict[str, str]:
        """Convert to environment variables dict for ClaudeAgentOptions."""
        env: dict[str, str] = {}
        auth_token = self.auth_token
        if auth_token is not None:
            env["ANTHROPIC_AUTH_TOKEN"] = auth_token
        base_url = self.base_url
        if base_url is not None:
            env["ANTHROPIC_BASE_URL"] = base_url
        model = self.model
        if model is not None:
            env["ANTHROPIC_MODEL"] = model
        return env


@dataclass
class AgentConfig:
    """DevTeam Agent configuration."""
    gitlab: GitLabConfig
    jira: JiraConfig
    claude: ClaudeConfig
    reports_dir: str
    team_members: list[str]  # List of team member names

    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Load agent config from environment variables."""
        gitlab = GitLabConfig.from_env()
        jira = JiraConfig.from_env()
        claude = ClaudeConfig.from_env()

        # Reports directory, default to data/reports
        reports_dir = os.getenv("REPORTS_DIR", "data/reports")

        # Team members (comma-separated)
        team_members_str = os.getenv("TEAM_MEMBERS")
        if not team_members_str:
            raise ValueError("TEAM_MEMBERS must be set in environment variables (comma-separated names)")

        team_members = [name.strip() for name in team_members_str.split(",")]

        return cls(
            gitlab=gitlab,
            jira=jira,
            claude=claude,
            reports_dir=reports_dir,
            team_members=team_members
        )
