"""MCP tools for GitLab integration."""

from typing import Any
from datetime import date


def create_gitlab_tools(gitlab_client):
    """Create GitLab integration tools."""
    from claude_agent_sdk import tool

    @tool(
        "get_gitlab_user_activity",
        "Get a user's GitLab activity (commits, MRs, issues) for a date range",
        {
            "username": str,
            "start_date": str,  # ISO format: YYYY-MM-DD
            "end_date": str     # ISO format: YYYY-MM-DD
        }
    )
    async def get_gitlab_user_activity(args: dict[str, Any]):
        """Get GitLab user activity."""
        username = args["username"]
        start_date = date.fromisoformat(args["start_date"])
        end_date = date.fromisoformat(args["end_date"])

        activity = await gitlab_client.get_user_activity(username, start_date, end_date)

        if "error" in activity:
            return {
                "content": [{
                    "type": "text",
                    "text": f"错误: {activity['error']}"
                }]
            }

        # Format output
        summary = activity["summary"]
        output = f"**{username} 的 GitLab 活动** ({start_date} 至 {end_date})\n\n"
        output += f"- 提交: {summary['total_commits']}\n"
        output += f"- 合并请求: {summary['total_merge_requests']}\n"
        output += f"- Issues: {summary['total_issues']}\n\n"

        if activity["commits"]:
            output += "**提交列表**:\n"
            for commit in activity["commits"][:10]:  # Limit to 10
                output += f"- `{commit['sha']}` {commit['title']}\n"
            if len(activity["commits"]) > 10:
                output += f"- ... 及其他 {len(activity['commits']) - 10} 次提交\n"
            output += "\n"

        if activity["merge_requests"]:
            output += "**合并请求**:\n"
            for mr in activity["merge_requests"]:
                state = mr['state']
                output += f"- !{mr['iid']} [{state}] {mr['title']}\n"
            output += "\n"

        if activity["issues"]:
            output += "**Issues**:\n"
            for issue in activity["issues"]:
                state = issue['state']
                output += f"- #{issue['iid']} [{state}] {issue['title']}\n"

        return {
            "content": [{
                "type": "text",
                "text": output
            }]
        }

    @tool(
        "get_gitlab_issue_details",
        "Get detailed information about a GitLab issue",
        {
            "project_id": int,
            "issue_iid": int
        }
    )
    async def get_gitlab_issue_details(args: dict[str, Any]):
        """Get GitLab issue details."""
        project_id = args["project_id"]
        issue_iid = args["issue_iid"]

        details = await gitlab_client.get_issue_details(project_id, issue_iid)

        if not details:
            return {
                "content": [{
                    "type": "text",
                    "text": f"未找到 issue #{issue_iid} (project {project_id})"
                }]
            }

        output = f"**Issue #{issue_iid}**: {details['title']}\n\n"
        output += f"**状态**: {details['state']}\n"
        output += f"**创建时间**: {details['created_at']}\n"
        output += f"**更新时间**: {details['updated_at']}\n"

        if details['closed_at']:
            output += f"**关闭时间**: {details['closed_at']}\n"

        if details['labels']:
            output += f"**标签**: {', '.join(details['labels'])}\n"

        if details['assignees']:
            output += f"**分配给**: {', '.join(details['assignees'])}\n"

        output += f"\n**描述**:\n{details['description']}\n"
        output += f"\n**链接**: {details['web_url']}"

        return {
            "content": [{
                "type": "text",
                "text": output
            }]
        }

    return [get_gitlab_user_activity, get_gitlab_issue_details]