"""MCP tools for weekly report management."""

from datetime import datetime, date
from typing import Any
import json


def create_report_tools(report_manager, report_generator, config):
    """Create report management tools."""
    from claude_agent_sdk import tool

    @tool(
        "read_weekly_report",
        "Read a team member's weekly report for a specific week",
        {
            "year": int,
            "month": int,
            "week_num": int,
            "member_name": str
        }
    )
    async def read_weekly_report(args: dict[str, Any]):
        """Read a specific member's weekly report."""
        year = args["year"]
        month = args["month"]
        week_num = args["week_num"]
        member_name = args["member_name"]

        content = report_manager.read_report(year, month)
        member_report = report_manager.get_member_report(content, week_num, member_name)

        if member_report:
            return {
                "content": [{
                    "type": "text",
                    "text": f"## {member_name} 的第{week_num}周周报\n\n{member_report}"
                }]
            }
        else:
            return {
                "content": [{
                    "type": "text",
                    "text": f"未找到 {member_name} 在 {year}年{month}月第{week_num}周的周报。"
                }]
            }

    @tool(
        "update_weekly_report",
        "Update or create a team member's weekly report",
        {
            "year": int,
            "month": int,
            "week_num": int,
            "member_name": str,
            "report_content": str
        }
    )
    async def update_weekly_report(args: dict[str, Any]):
        """Update or create a member's weekly report."""
        year = args["year"]
        month = args["month"]
        week_num = args["week_num"]
        member_name = args["member_name"]
        report_content = args["report_content"]

        report_manager.add_or_update_member_report(
            year, month, week_num, member_name, report_content
        )

        return {
            "content": [{
                "type": "text",
                "text": f"已更新 {member_name} 在 {year}年{month}月第{week_num}周的周报。"
            }]
        }

    @tool(
        "generate_weekly_report",
        "Auto-generate a weekly report for a team member from GitLab and Jira",
        {
            "member_name": str,
            "gitlab_username": str,
            "jira_username": str,
            "year": int,
            "month": int,
            "week_num": int,
            "start_date": str,  # ISO format: YYYY-MM-DD
            "end_date": str     # ISO format: YYYY-MM-DD
        }
    )
    async def generate_weekly_report(args: dict[str, Any]):
        """Generate a weekly report from GitLab and Jira activity."""
        member_name = args["member_name"]
        gitlab_username = args["gitlab_username"]
        jira_username = args["jira_username"]
        year = args["year"]
        month = args["month"]
        week_num = args["week_num"]
        start_date = date.fromisoformat(args["start_date"])
        end_date = date.fromisoformat(args["end_date"])

        # Generate report
        report_content = await report_generator.generate_member_weekly_report(
            member_name, gitlab_username, jira_username, start_date, end_date
        )

        # Save to file
        report_manager.add_or_update_member_report(
            year, month, week_num, member_name, report_content
        )

        return {
            "content": [{
                "type": "text",
                "text": f"""已生成并保存 {member_name} 在第{week_num}周的周报:

{report_content}

⚠️ **重要**: 请根据以上活动数据，撰写一段简洁的总结（3-4句话），然后使用 `update_weekly_report` 工具将总结内容替换掉 "*[待 Agent 根据以上活动数据生成总结]*" 这段占位符。

总结应包含：本周主要完成的工作、工作重点/亮点。"""
            }]
        }

    @tool(
        "read_month_report",
        "Read the entire monthly report file",
        {
            "year": int,
            "month": int
        }
    )
    async def read_month_report(args: dict[str, Any]):
        """Read the full monthly report."""
        year = args["year"]
        month = args["month"]

        content = report_manager.read_report(year, month)

        if content:
            return {
                "content": [{
                    "type": "text",
                    "text": content
                }]
            }
        else:
            return {
                "content": [{
                    "type": "text",
                    "text": f"{year}年{month}月的报告文件不存在或为空。"
                }]
            }

    @tool(
        "list_reports",
        "List all available monthly reports",
        {}
    )
    async def list_reports(args: dict[str, Any]):
        """List all available reports."""
        reports = report_manager.list_reports()

        if reports:
            report_list = "\n".join([f"- {year}年{month}月" for year, month in reports])
            return {
                "content": [{
                    "type": "text",
                    "text": f"可用的报告:\n{report_list}"
                }]
            }
        else:
            return {
                "content": [{
                    "type": "text",
                    "text": "暂无任何报告。"
                }]
            }

    return [
        read_weekly_report,
        update_weekly_report,
        generate_weekly_report,
        read_month_report,
        list_reports
    ]