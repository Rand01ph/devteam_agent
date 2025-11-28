"""Weekly report generator."""

from datetime import date, timedelta
from typing import Optional
from ..integrations.gitlab_client import GitLabClient
from ..integrations.jira_client import JiraClient


class ReportGenerator:
    """Generates weekly reports from GitLab and Jira data."""

    def __init__(self, gitlab_client: GitLabClient, jira_client: JiraClient):
        """
        Initialize report generator.

        Args:
            gitlab_client: GitLab client instance
            jira_client: Jira client instance
        """
        self.gitlab = gitlab_client
        self.jira = jira_client

    async def generate_member_weekly_report(
        self,
        member_name: str,
        gitlab_username: str,
        jira_username: str,
        start_date: date,
        end_date: date
    ) -> str:
        """
        Generate a weekly report for a team member.

        Args:
            member_name: Display name of team member
            gitlab_username: GitLab username
            jira_username: Jira username
            start_date: Start date of the week
            end_date: End date of the week

        Returns:
            Markdown formatted report
        """
        # Get GitLab activity
        gitlab_activity = await self.gitlab.get_user_activity(gitlab_username, start_date, end_date)

        # Get Jira activity
        jira_activity = await self.jira.get_user_activity(jira_username, start_date, end_date)

        # Format report
        report_lines = []

        # Summary section
        report_lines.append("### 本周工作总结\n")

        # GitLab section
        if gitlab_activity["summary"]["total_commits"] > 0:
            report_lines.append(f"**代码提交**: {gitlab_activity['summary']['total_commits']} 次提交")
            for commit in gitlab_activity["commits"][:5]:  # Show first 5
                report_lines.append(f"  - `{commit['sha']}` {commit['title']} - [查看]({commit['web_url']})")
            if len(gitlab_activity["commits"]) > 5:
                report_lines.append(f"  - ... 及其他 {len(gitlab_activity['commits']) - 5} 次提交")
            report_lines.append("")

        if gitlab_activity["summary"]["total_merge_requests"] > 0:
            report_lines.append(f"**合并请求**: {gitlab_activity['summary']['total_merge_requests']} 个 MR")
            for mr in gitlab_activity["merge_requests"]:
                state_emoji = "✅" if mr["state"] == "merged" else "🔄" if mr["state"] == "opened" else "❌"
                report_lines.append(f"  - {state_emoji} !{mr['iid']} {mr['title']} - [查看]({mr['web_url']})")
            report_lines.append("")

        if gitlab_activity["summary"]["total_issues"] > 0:
            report_lines.append(f"**GitLab Issues**: {gitlab_activity['summary']['total_issues']} 个问题")
            for issue in gitlab_activity["issues"]:
                state_emoji = "✅" if issue["state"] == "closed" else "🔄"
                report_lines.append(f"  - {state_emoji} #{issue['iid']} {issue['title']} - [查看]({issue['web_url']})")
            report_lines.append("")

        # Jira section
        if jira_activity["summary"]["total_assigned"] > 0 or jira_activity["summary"]["total_reported"] > 0:
            report_lines.append(f"**Jira Issues**: 分配 {jira_activity['summary']['total_assigned']} 个, 创建 {jira_activity['summary']['total_reported']} 个")

            # Show all involved issues
            for issue in jira_activity["all_issues"]:
                type_emoji = "🐛" if "bug" in issue["type"].lower() else "✨" if "feature" in issue["type"].lower() else "📋"
                status_emoji = "✅" if issue["status"].lower() in ["done", "closed"] else "🔄"
                report_lines.append(f"  - {type_emoji} {status_emoji} [{issue['key']}]({issue['url']}) {issue['summary']}")
            report_lines.append("")

        # If no activity
        if not report_lines:
            report_lines.append("本周暂无记录的活动。\n")

        return "\n".join(report_lines)

    async def generate_team_weekly_summary(
        self,
        week_content: str
    ) -> str:
        """
        Generate a summary of the entire team's weekly work.

        Args:
            week_content: Full week section content from markdown

        Returns:
            Summary text (to be used by LLM or as-is)
        """
        # This will be enhanced by the LLM when called via Agent tools
        # For now, just return a basic structure
        return f"## 团队本周总结\n\n{week_content}\n"

    async def generate_monthly_summary(
        self,
        month_content: str
    ) -> str:
        """
        Generate a summary of the entire team's monthly work.

        Args:
            month_content: Full month content from markdown

        Returns:
            Summary text (to be used by LLM or as-is)
        """
        # This will be enhanced by the LLM when called via Agent tools
        return f"## 团队本月总结\n\n{month_content}\n"

    def format_date_range(self, start_date: date, end_date: date) -> str:
        """Format a date range for display."""
        return f"{start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}"