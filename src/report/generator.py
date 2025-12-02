"""Weekly report generator."""

from datetime import date
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
        # Get GitLab activity (using /users/:id/events API)
        gitlab_activity = await self.gitlab.get_user_activity(gitlab_username, start_date, end_date)

        # Get Jira activity
        jira_activity = await self.jira.get_user_activity(jira_username, start_date, end_date)

        # Format report
        report_lines = []

        # Summary section
        report_lines.append("### 本周工作总结\n")

        has_content = False

        # GitLab Push Events (代码提交)
        if gitlab_activity["summary"]["total_pushes"] > 0:
            has_content = True
            total_commits = gitlab_activity["summary"]["total_commits"]
            total_pushes = gitlab_activity["summary"]["total_pushes"]
            report_lines.append(f"**代码推送**: {total_pushes} 次推送 (共 {total_commits} 次提交)")

            for push in gitlab_activity["push_events"]:  # Show all
                commit_count = push.get("commit_count", 1)
                ref = push.get("ref", "unknown")
                commit_title = push.get("commit_title", "")
                report_lines.append(f"  - 推送 {commit_count} 个提交到 `{ref}`: {commit_title}")

            report_lines.append("")

        # GitLab MR Events (合并请求)
        if gitlab_activity["summary"]["total_merge_requests"] > 0:
            has_content = True
            report_lines.append(f"**合并请求活动**: {gitlab_activity['summary']['total_merge_requests']} 个 MR 相关事件")

            for mr in gitlab_activity["merge_request_events"]:  # Show all
                action = mr.get("action_name", "操作")
                title = mr.get("target_title", "")
                iid = mr.get("target_iid", "")
                action_emoji = self._get_action_emoji(action)
                report_lines.append(f"  - {action_emoji} {action} MR !{iid}: {title}")

            report_lines.append("")

        # GitLab Issue Events
        if gitlab_activity["summary"]["total_issues"] > 0:
            has_content = True
            report_lines.append(f"**GitLab Issue 活动**: {gitlab_activity['summary']['total_issues']} 个 Issue 相关事件")

            for issue in gitlab_activity["issue_events"]:  # Show all
                action = issue.get("action_name", "操作")
                title = issue.get("target_title", "")
                iid = issue.get("target_iid", "")
                action_emoji = self._get_action_emoji(action)
                report_lines.append(f"  - {action_emoji} {action} Issue #{iid}: {title}")

            report_lines.append("")

        # GitLab Comments
        if gitlab_activity["summary"]["total_comments"] > 0:
            has_content = True
            report_lines.append(f"**评论活动**: {gitlab_activity['summary']['total_comments']} 条评论")

            for comment in gitlab_activity["comment_events"]:  # Show all
                noteable_type = comment.get("noteable_type", "")
                note_body = comment.get("note_body", "")[:80]
                suffix = "..." if len(comment.get("note_body", "")) > 80 else ""
                report_lines.append(f"  - 在 {noteable_type} 上评论: {note_body}{suffix}")

            report_lines.append("")

        # Jira section - Worklogs (工时统计)
        jira_summary = jira_activity["summary"]
        if jira_summary.get("total_worklog_entries", 0) > 0:
            has_content = True
            report_lines.append(f"**Jira 工时**: {jira_summary['total_time_spent_formatted']}")

            # Group worklogs by issue for cleaner display
            worklogs_by_issue = {}
            for log in jira_activity.get("worklogs", []):
                key = log["issue_key"]
                if key not in worklogs_by_issue:
                    worklogs_by_issue[key] = {
                        "summary": log["issue_summary"],
                        "total_seconds": 0,
                        "entries": []
                    }
                worklogs_by_issue[key]["total_seconds"] += log["time_spent_seconds"]
                worklogs_by_issue[key]["entries"].append(log)

            # Show all issues sorted by time spent
            sorted_issues = sorted(
                worklogs_by_issue.items(),
                key=lambda x: x[1]["total_seconds"],
                reverse=True
            )

            for issue_key, data in sorted_issues:  # Show all
                hours = data["total_seconds"] // 3600
                minutes = (data["total_seconds"] % 3600) // 60
                time_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
                report_lines.append(f"  - [{issue_key}]({self.jira.url}/browse/{issue_key}) **{time_str}**: {data['summary']}")

            report_lines.append("")

        # Jira Issues section
        if jira_summary["total_assigned"] > 0 or jira_summary["total_reported"] > 0:
            has_content = True
            report_lines.append(f"**Jira Issues**: 分配 {jira_summary['total_assigned']} 个, 创建 {jira_summary['total_reported']} 个")

            # Show all involved issues
            for issue in jira_activity["all_issues"]:  # Show all
                issue_type = issue.get("type") or ""
                status = issue.get("status") or "N/A"
                type_emoji = self._get_issue_type_emoji(issue_type)
                status_emoji = "✅" if status.lower() in ["done", "closed", "resolved"] else "🔄"
                report_lines.append(f"  - {type_emoji} {status_emoji} [{issue['key']}]({issue['url']}) {issue['summary']}")

            report_lines.append("")

        # If no activity
        if not has_content:
            report_lines.append("本周暂无记录的活动。\n")

        # Agent summary section placeholder
        report_lines.append("### 🤖 Agent 总结\n")
        report_lines.append("*[待 Agent 根据以上活动数据生成总结]*\n")

        return "\n".join(report_lines)

    def _get_action_emoji(self, action: str) -> str:
        """Get emoji for GitLab action."""
        action_lower = action.lower()
        if "closed" in action_lower or "merged" in action_lower:
            return "✅"
        elif "opened" in action_lower or "created" in action_lower:
            return "🆕"
        elif "approved" in action_lower:
            return "👍"
        elif "commented" in action_lower:
            return "💬"
        else:
            return "🔄"

    def _get_issue_type_emoji(self, issue_type: str) -> str:
        """Get emoji for issue type."""
        type_lower = issue_type.lower()
        if "bug" in type_lower:
            return "🐛"
        elif "feature" in type_lower or "story" in type_lower:
            return "✨"
        elif "task" in type_lower:
            return "📋"
        elif "improvement" in type_lower:
            return "🔧"
        else:
            return "📝"

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
