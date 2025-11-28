"""MCP tools for Jira integration."""

from typing import Any
from datetime import date


def create_jira_tools(jira_client):
    """Create Jira integration tools."""
    from claude_agent_sdk import tool

    @tool(
        "get_jira_user_activity",
        "Get a user's Jira activity (issues) for a date range",
        {
            "username": str,
            "start_date": str,  # ISO format: YYYY-MM-DD
            "end_date": str     # ISO format: YYYY-MM-DD
        }
    )
    async def get_jira_user_activity(args: dict[str, Any]):
        """Get Jira user activity."""
        username = args["username"]
        start_date = date.fromisoformat(args["start_date"])
        end_date = date.fromisoformat(args["end_date"])

        activity = await jira_client.get_user_activity(username, start_date, end_date)

        summary = activity["summary"]
        output = f"**{username} 的 Jira 活动** ({start_date} 至 {end_date})\n\n"
        output += f"- 分配的 Issues: {summary['total_assigned']}\n"
        output += f"- 创建的 Issues: {summary['total_reported']}\n"
        output += f"- 涉及的 Issues: {summary['total_involved']}\n\n"

        if activity["all_issues"]:
            output += "**Issues 列表**:\n"
            for issue in activity["all_issues"]:
                output += f"- [{issue['key']}]({issue['url']}) [{issue['status']}] {issue['summary']}\n"
                output += f"  - 类型: {issue['type']}, 优先级: {issue['priority']}\n"

        return {
            "content": [{
                "type": "text",
                "text": output
            }]
        }

    @tool(
        "get_jira_issue_details",
        "Get detailed information about a Jira issue",
        {
            "issue_key": str  # e.g., PROJ-123
        }
    )
    async def get_jira_issue_details(args: dict[str, Any]):
        """Get Jira issue details."""
        issue_key = args["issue_key"]

        details = await jira_client.get_issue_details(issue_key)

        if not details:
            return {
                "content": [{
                    "type": "text",
                    "text": f"未找到 issue {issue_key}"
                }]
            }

        output = f"**Issue {details['key']}**: {details['summary']}\n\n"
        output += f"**状态**: {details['status']}\n"
        output += f"**类型**: {details['type']}\n"
        output += f"**优先级**: {details['priority']}\n"
        output += f"**创建时间**: {details['created']}\n"
        output += f"**更新时间**: {details['updated']}\n"

        if details['assignee']:
            output += f"**分配给**: {details['assignee']}\n"

        if details['reporter']:
            output += f"**报告人**: {details['reporter']}\n"

        if details['labels']:
            output += f"**标签**: {', '.join(details['labels'])}\n"

        output += f"\n**描述**:\n{details['description']}\n"

        if details['comments']:
            output += f"\n**评论** ({len(details['comments'])} 条):\n"
            for comment in details['comments'][:5]:  # Show first 5
                output += f"- {comment['author']} ({comment['created']}): {comment['body'][:100]}...\n"

        output += f"\n**链接**: {details['url']}"

        return {
            "content": [{
                "type": "text",
                "text": output
            }]
        }

    return [get_jira_user_activity, get_jira_issue_details]