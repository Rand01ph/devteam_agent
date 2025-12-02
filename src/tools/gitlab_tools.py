"""MCP tools for GitLab integration."""

from typing import Any
from datetime import date


def create_gitlab_tools(gitlab_client):
    """Create GitLab integration tools."""
    from claude_agent_sdk import tool

    @tool(
        "get_gitlab_user_activity",
        "Get a user's GitLab contribution events (pushes, MRs, issues, comments) for a date range",
        {
            "username": str,
            "start_date": str,  # ISO format: YYYY-MM-DD
            "end_date": str     # ISO format: YYYY-MM-DD
        }
    )
    async def get_gitlab_user_activity(args: dict[str, Any]):
        """Get GitLab user activity using the /users/:id/events API."""
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
        output += f"- 总事件数: {summary['total_events']}\n"
        output += f"- Push 次数: {summary['total_pushes']} (共 {summary['total_commits']} 次提交)\n"
        output += f"- MR 相关事件: {summary['total_merge_requests']}\n"
        output += f"- Issue 相关事件: {summary['total_issues']}\n"
        output += f"- 评论: {summary['total_comments']}\n\n"

        # Push events (code commits)
        if activity["push_events"]:
            output += "**代码推送**:\n"
            for push in activity["push_events"][:10]:
                commit_count = push.get("commit_count", 1)
                ref = push.get("ref", "unknown")
                commit_title = push.get("commit_title", "")
                output += f"- 推送 {commit_count} 个提交到 `{ref}`: {commit_title}\n"
            if len(activity["push_events"]) > 10:
                output += f"- ... 及其他 {len(activity['push_events']) - 10} 次推送\n"
            output += "\n"

        # Merge request events
        if activity["merge_request_events"]:
            output += "**合并请求活动**:\n"
            for mr in activity["merge_request_events"][:10]:
                action = mr.get("action_name", "操作")
                title = mr.get("target_title", "")
                iid = mr.get("target_iid", "")
                output += f"- {action} MR !{iid}: {title}\n"
            if len(activity["merge_request_events"]) > 10:
                output += f"- ... 及其他 {len(activity['merge_request_events']) - 10} 个 MR 事件\n"
            output += "\n"

        # Issue events
        if activity["issue_events"]:
            output += "**Issue 活动**:\n"
            for issue in activity["issue_events"][:10]:
                action = issue.get("action_name", "操作")
                title = issue.get("target_title", "")
                iid = issue.get("target_iid", "")
                output += f"- {action} Issue #{iid}: {title}\n"
            if len(activity["issue_events"]) > 10:
                output += f"- ... 及其他 {len(activity['issue_events']) - 10} 个 Issue 事件\n"
            output += "\n"

        # Comment events
        if activity["comment_events"]:
            output += "**评论活动**:\n"
            for comment in activity["comment_events"][:5]:
                noteable_type = comment.get("noteable_type", "")
                note_body = comment.get("note_body", "")[:100]
                output += f"- 在 {noteable_type} 上评论: {note_body}...\n"
            if len(activity["comment_events"]) > 5:
                output += f"- ... 及其他 {len(activity['comment_events']) - 5} 条评论\n"
            output += "\n"

        # Other events
        if activity.get("other_events"):
            output += f"**其他活动**: {len(activity['other_events'])} 个事件\n"

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

        output = f"**Issue #{details['iid']}**: {details['title']}\n\n"
        output += f"**状态**: {details['state']}\n"
        output += f"**作者**: {details.get('author', 'N/A')}\n"
        output += f"**创建时间**: {details['created_at']}\n"
        output += f"**更新时间**: {details['updated_at']}\n"

        if details.get('closed_at'):
            output += f"**关闭时间**: {details['closed_at']}\n"

        if details.get('labels'):
            output += f"**标签**: {', '.join(details['labels'])}\n"

        if details.get('assignees'):
            output += f"**分配给**: {', '.join(details['assignees'])}\n"

        if details.get('description'):
            output += f"\n**描述**:\n{details['description']}\n"

        output += f"\n**链接**: {details['web_url']}"

        return {
            "content": [{
                "type": "text",
                "text": output
            }]
        }

    @tool(
        "get_gitlab_mr_details",
        "Get detailed information about a GitLab merge request",
        {
            "project_id": int,
            "mr_iid": int
        }
    )
    async def get_gitlab_mr_details(args: dict[str, Any]):
        """Get GitLab merge request details."""
        project_id = args["project_id"]
        mr_iid = args["mr_iid"]

        details = await gitlab_client.get_merge_request_details(project_id, mr_iid)

        if not details:
            return {
                "content": [{
                    "type": "text",
                    "text": f"未找到 MR !{mr_iid} (project {project_id})"
                }]
            }

        output = f"**MR !{details['iid']}**: {details['title']}\n\n"
        output += f"**状态**: {details['state']}\n"
        output += f"**作者**: {details.get('author', 'N/A')}\n"
        output += f"**分支**: `{details['source_branch']}` → `{details['target_branch']}`\n"
        output += f"**创建时间**: {details['created_at']}\n"
        output += f"**更新时间**: {details['updated_at']}\n"

        if details.get('merged_at'):
            output += f"**合并时间**: {details['merged_at']}\n"

        if details.get('labels'):
            output += f"**标签**: {', '.join(details['labels'])}\n"

        if details.get('assignees'):
            output += f"**分配给**: {', '.join(details['assignees'])}\n"

        if details.get('description'):
            output += f"\n**描述**:\n{details['description']}\n"

        output += f"\n**链接**: {details['web_url']}"

        return {
            "content": [{
                "type": "text",
                "text": output
            }]
        }

    return [get_gitlab_user_activity, get_gitlab_issue_details, get_gitlab_mr_details]
