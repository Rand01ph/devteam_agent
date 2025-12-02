"""MCP tools for Jira integration."""

from typing import Any
from datetime import date


def create_jira_tools(jira_client):
    """Create Jira integration tools."""
    from claude_agent_sdk import tool

    @tool(
        "get_jira_user_activity",
        "Get a user's Jira activity (issues and worklogs) for a date range",
        {
            "username": str,
            "start_date": str,  # ISO format: YYYY-MM-DD
            "end_date": str     # ISO format: YYYY-MM-DD
        }
    )
    async def get_jira_user_activity(args: dict[str, Any]):
        """Get Jira user activity including worklogs."""
        username = args["username"]
        start_date = date.fromisoformat(args["start_date"])
        end_date = date.fromisoformat(args["end_date"])

        activity = await jira_client.get_user_activity(username, start_date, end_date)

        summary = activity["summary"]
        output = f"**{username} 的 Jira 活动** ({start_date} 至 {end_date})\n\n"

        # Summary section
        output += "### 概览\n"
        output += f"- 分配的 Issues: {summary['total_assigned']}\n"
        output += f"- 创建的 Issues: {summary['total_reported']}\n"
        output += f"- 涉及的 Issues: {summary['total_involved']}\n"
        output += f"- 工作日志记录: {summary['total_worklog_entries']} 条\n"
        output += f"- **总工时**: {summary['total_time_spent_formatted']}\n\n"

        # Worklogs section
        if activity.get("worklogs"):
            output += "### 工作日志\n"
            for log in activity["worklogs"][:15]:  # Show first 15
                output += f"- [{log['issue_key']}]({jira_client.url}/browse/{log['issue_key']}) "
                output += f"**{log['time_spent']}** ({log['started_date']})\n"
                output += f"  - {log['issue_summary'][:60]}{'...' if len(log['issue_summary']) > 60 else ''}\n"
                if log.get("comment"):
                    output += f"  - 备注: {log['comment'][:50]}{'...' if len(log.get('comment', '')) > 50 else ''}\n"

            if len(activity["worklogs"]) > 15:
                output += f"- ... 及其他 {len(activity['worklogs']) - 15} 条工作日志\n"
            output += "\n"

        # Issues section
        if activity.get("all_issues"):
            output += "### 相关 Issues\n"
            for issue in activity["all_issues"][:10]:
                status = issue.get('status') or 'N/A'
                issue_type = issue.get('type') or 'N/A'
                output += f"- [{issue['key']}]({issue['url']}) [{status}] {issue['summary']}\n"
                output += f"  - 类型: {issue_type}\n"

            if len(activity["all_issues"]) > 10:
                output += f"- ... 及其他 {len(activity['all_issues']) - 10} 个 Issues\n"

        return {
            "content": [{
                "type": "text",
                "text": output
            }]
        }

    @tool(
        "get_jira_worklog_summary",
        "Get user's worklog summary grouped by project for a date range",
        {
            "username": str,
            "start_date": str,  # ISO format: YYYY-MM-DD
            "end_date": str     # ISO format: YYYY-MM-DD
        }
    )
    async def get_jira_worklog_summary(args: dict[str, Any]):
        """Get worklog summary by project."""
        username = args["username"]
        start_date = date.fromisoformat(args["start_date"])
        end_date = date.fromisoformat(args["end_date"])

        summary = await jira_client.get_worklog_summary_by_project(username, start_date, end_date)

        output = f"**{username} 的工时统计** ({start_date} 至 {end_date})\n\n"
        output += f"**总工时**: {summary['total_time_formatted']}\n\n"

        if summary["projects"]:
            output += "### 按项目分布\n"
            output += "| 项目 | 工时 | Issue数 | 日志条数 |\n"
            output += "|------|------|---------|----------|\n"
            for proj in summary["projects"]:
                output += f"| {proj['project_key']} | {proj['total_time_formatted']} | {proj['issue_count']} | {proj['worklog_count']} |\n"
        else:
            output += "该时间段内没有工时记录。\n"

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

        if details.get('assignee'):
            output += f"**分配给**: {details['assignee']}\n"

        if details.get('reporter'):
            output += f"**报告人**: {details['reporter']}\n"

        if details.get('parent_key'):
            output += f"**父 Issue**: {details['parent_key']}\n"

        if details.get('labels'):
            output += f"**标签**: {', '.join(details['labels'])}\n"

        # Time tracking info
        if details.get('time_estimate') or details.get('time_spent'):
            output += "\n**时间跟踪**:\n"
            if details.get('time_estimate'):
                output += f"  - 预估: {details['time_estimate']}\n"
            if details.get('time_spent'):
                output += f"  - 已花费: {details['time_spent']}\n"
            if details.get('time_remaining'):
                output += f"  - 剩余: {details['time_remaining']}\n"

        if details.get('description'):
            desc = details['description']
            if len(desc) > 500:
                desc = desc[:500] + "..."
            output += f"\n**描述**:\n{desc}\n"

        if details.get('comments'):
            output += f"\n**评论** ({len(details['comments'])} 条):\n"
            for comment in details['comments'][:5]:  # Show first 5
                body = comment['body'][:100] + "..." if len(comment['body']) > 100 else comment['body']
                output += f"- {comment['author']} ({comment['created'][:10]}): {body}\n"
            if len(details['comments']) > 5:
                output += f"- ... 及其他 {len(details['comments']) - 5} 条评论\n"

        output += f"\n**链接**: {details['url']}"

        return {
            "content": [{
                "type": "text",
                "text": output
            }]
        }

    return [get_jira_user_activity, get_jira_worklog_summary, get_jira_issue_details]
