"""MCP tools for weekly report management."""

from datetime import date
from typing import Any


def create_report_tools(report_manager, report_generator, config):
    """Create report management tools."""
    from claude_agent_sdk import tool

    @tool(
        "finalize_weekly_report",
        "Run the weekly report preparation pipeline: ensure the week directory exists and organize _pending.md into member reports. After this tool returns, the main agent should continue with subagents to generate personal summaries and the team summary.",
        {
            "year": int,
            "month": int,
            "week_num": int,
            "start_date": str,  # ISO format: YYYY-MM-DD (required when the week directory does not exist yet)
            "end_date": str     # ISO format: YYYY-MM-DD (required when the week directory does not exist yet)
        }
    )
    async def finalize_weekly_report(args: dict[str, Any]):
        """Prepare one week's reports for subagent-based summarization."""
        year = args["year"]
        month = args["month"]
        week_num = args["week_num"]
        start_date_str = args.get("start_date")
        end_date_str = args.get("end_date")

        start_date = date.fromisoformat(start_date_str) if start_date_str else None
        end_date = date.fromisoformat(end_date_str) if end_date_str else None

        week_dir = report_manager.get_week_dir(year, month, week_num)
        if week_dir is None:
            if not start_date or not end_date:
                return {
                    "content": [{
                        "type": "text",
                        "text": (
                            f"执行失败: 第{week_num}周目录不存在，且未提供 start_date / end_date 来创建目录。"
                        )
                    }]
                }

            prepared = report_manager.prepare_week_report_directory(
                year,
                month,
                week_num,
                start_date=start_date,
                end_date=end_date,
            )
            week_dir = report_manager.get_week_dir(year, month, week_num)
        else:
            prepared = None

        organize_result = None
        pending_file = week_dir / "_pending.md"
        if pending_file.exists() and pending_file.read_text(encoding="utf-8").strip():
            organize_result = report_manager.organize_week_content(
                year,
                month,
                week_num,
                start_date=start_date,
                end_date=end_date,
            )
            if not organize_result["success"]:
                return {
                    "content": [{
                        "type": "text",
                        "text": f"执行失败: {organize_result['error']}"
                    }]
                }

        member_reports = report_manager.get_week_member_reports(year, month, week_num)
        if not member_reports:
            return {
                "content": [{
                    "type": "text",
                    "text": f"执行失败: 第{week_num}周没有可汇总的成员周报。"
                }]
            }

        message_lines = [f"已完成第{week_num}周固定流水线。"]
        if prepared:
            message_lines.append(prepared["message"])
        if organize_result:
            message_lines.append(organize_result["message"])
        else:
            message_lines.append("未检测到待整理输入稿，当前成员周报保持不变。")
        message_lines.append(f"已汇总成员: {', '.join(member_reports.keys())}")
        message_lines.append("下一步：调用 `read_weekly_report_bundle` 获取完整周报上下文，再使用 `member-personal-summarizer` 和 `team-weekly-summarizer` 子代理生成总结并分别写回。")

        return {
            "content": [{
                "type": "text",
                "text": "\n".join(message_lines),
            }]
        }

    @tool(
        "prepare_week_report_directory",
        "Prepare the target week's report directory, metadata file, and _pending.md template before team members' raw weekly reports are pasted in.",
        {
            "year": int,
            "month": int,
            "week_num": int,
            "start_date": str,  # ISO format: YYYY-MM-DD
            "end_date": str,    # ISO format: YYYY-MM-DD
        }
    )
    async def prepare_week_report_directory(args: dict[str, Any]):
        """Prepare a week report directory and pending template."""
        year = args["year"]
        month = args["month"]
        week_num = args["week_num"]
        start_date = date.fromisoformat(args["start_date"])
        end_date = date.fromisoformat(args["end_date"])

        result = report_manager.prepare_week_report_directory(
            year,
            month,
            week_num,
            start_date=start_date,
            end_date=end_date,
        )

        return {
            "content": [{
                "type": "text",
                "text": result["message"],
            }]
        }

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
        "read_weekly_report_bundle",
        "Read the full weekly report context for subagent summarization, including week label and all member reports.",
        {
            "year": int,
            "month": int,
            "week_num": int,
        }
    )
    async def read_weekly_report_bundle(args: dict[str, Any]):
        """Read the full weekly report context."""
        year = args["year"]
        month = args["month"]
        week_num = args["week_num"]

        meta = report_manager.get_week_metadata(year, month, week_num) or {}
        week_label = ""
        if meta.get("start_date") and meta.get("end_date"):
            start_date_obj = date.fromisoformat(meta["start_date"])
            end_date_obj = date.fromisoformat(meta["end_date"])
            week_label = f"{start_date_obj.month}.{start_date_obj.day}-{end_date_obj.month}.{end_date_obj.day}"

        member_reports = report_manager.get_week_member_reports(year, month, week_num)
        if not member_reports:
            return {
                "content": [{
                    "type": "text",
                    "text": f"未找到 {year}年{month}月第{week_num}周的成员周报。"
                }]
            }

        report_blocks = [f"# 周信息\n- week_num: {week_num}\n- week_label: {week_label or '-'}\n"]
        for member_name, report_content in member_reports.items():
            report_blocks.append(f"## {member_name}\n\n{report_content.strip()}")

        return {
            "content": [{
                "type": "text",
                "text": "\n\n".join(report_blocks)
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

        # Save to file with date range for week header
        report_manager.add_or_update_member_report(
            year, month, week_num, member_name, report_content,
            start_date=start_date, end_date=end_date
        )

        return {
            "content": [{
                "type": "text",
                "text": f"""已生成并保存 {member_name} 在第{week_num}周的周报:

{report_content}

⚠️ **重要**: 请根据以上工作明细，撰写一段简洁的总结（3-4句话），然后使用 `update_weekly_report` 工具将总结内容替换掉 "*[待 Agent 根据以下工作明细生成总结]*" 这段占位符。

总结应包含：本周主要完成的工作、工作重点/亮点。"""
            }]
        }

    @tool(
        "add_personal_summary",
        "Add or update a team member's personal summary for a specific week. This is used when team members submit their own weekly summary. If the member's report doesn't exist, it will create one.",
        {
            "year": int,
            "month": int,
            "week_num": int,
            "member_name": str,
            "personal_summary": str,  # The personal summary content from team member
            "start_date": str,  # ISO format: YYYY-MM-DD (optional, for week header)
            "end_date": str     # ISO format: YYYY-MM-DD (optional, for week header)
        }
    )
    async def add_personal_summary(args: dict[str, Any]):
        """Add or update a member's personal summary in their weekly report."""
        year = args["year"]
        month = args["month"]
        week_num = args["week_num"]
        member_name = args["member_name"]
        personal_summary = args["personal_summary"]
        start_date_str = args.get("start_date")
        end_date_str = args.get("end_date")

        # Parse dates if provided
        start_date = date.fromisoformat(start_date_str) if start_date_str else None
        end_date = date.fromisoformat(end_date_str) if end_date_str else None

        # Read existing report
        content = report_manager.read_report(year, month)
        member_report = report_manager.get_member_report(content, week_num, member_name)

        if not member_report:
            # Create a new report structure with personal summary
            new_report = f"""### 本周工作总结

#### 🤖 Agent 总结

*[待 Agent 生成总结]*

#### 个人总结

{personal_summary}

#### 工作明细

*[待生成工作明细]*
"""
            report_manager.add_or_update_member_report(
                year, month, week_num, member_name, new_report,
                start_date=start_date, end_date=end_date
            )
            return {
                "content": [{
                    "type": "text",
                    "text": f"已为 {member_name} 创建 {year}年{month}月第{week_num}周的周报，并添加了个人总结。"
                }]
            }

        # Replace personal summary placeholder or existing content
        import re
        # Match the personal summary section
        pattern = r"(#### 个人总结\n+)(\*\[待成员填写个人总结\]\*|[^\n#]*(?:\n(?!####)[^\n#]*)*)"
        replacement = f"#### 个人总结\n\n{personal_summary}\n"

        if re.search(pattern, member_report):
            updated_report = re.sub(pattern, replacement, member_report)
        else:
            # If no personal summary section exists, add it before work details
            work_details_pattern = r"(#### 工作明细)"
            if re.search(work_details_pattern, member_report):
                updated_report = re.sub(
                    work_details_pattern,
                    f"#### 个人总结\n\n{personal_summary}\n\n\\1",
                    member_report
                )
            else:
                # Just append if no work details section
                updated_report = member_report + f"\n#### 个人总结\n\n{personal_summary}\n"

        # Remove the member name header if present (it will be added by add_or_update_member_report)
        updated_report = re.sub(rf"^## {re.escape(member_name)}\n+", "", updated_report).strip()

        # Update the report file
        report_manager.add_or_update_member_report(
            year, month, week_num, member_name, updated_report,
            start_date=start_date, end_date=end_date
        )

        return {
            "content": [{
                "type": "text",
                "text": f"已更新 {member_name} 在 {year}年{month}月第{week_num}周的个人总结。"
            }]
        }

    @tool(
        "update_member_personal_summary",
        "Update only the `#### 个人总结` section for an existing weekly member report.",
        {
            "year": int,
            "month": int,
            "week_num": int,
            "member_name": str,
            "personal_summary": str,
        }
    )
    async def update_member_personal_summary(args: dict[str, Any]):
        """Update only the personal summary section of an existing member report."""
        result = report_manager.update_member_personal_summary(
            args["year"],
            args["month"],
            args["week_num"],
            args["member_name"],
            args["personal_summary"],
        )
        if result["success"]:
            return {"content": [{"type": "text", "text": result["message"]}]}
        return {"content": [{"type": "text", "text": f"更新失败: {result['error']}"}]}

    @tool(
        "organize_weekly_report",
        "Organize raw content from the target week's _pending.md file into member report files. It primarily uses account-name member sections such as '## huangjingfang'.",
        {
            "year": int,
            "month": int,
            "week_num": int,
            "start_date": str,  # ISO format: YYYY-MM-DD
            "end_date": str     # ISO format: YYYY-MM-DD
        }
    )
    async def organize_weekly_report(args: dict[str, Any]):
        """Organize raw weekly report content into proper structure."""
        year = args["year"]
        month = args["month"]
        week_num = args["week_num"]
        start_date = date.fromisoformat(args["start_date"])
        end_date = date.fromisoformat(args["end_date"])

        result = report_manager.organize_week_content(
            year, month, week_num,
            start_date=start_date, end_date=end_date
        )

        if result["success"]:
            return {
                "content": [{
                    "type": "text",
                    "text": result["message"]
                }]
            }
        else:
            return {
                "content": [{
                    "type": "text",
                    "text": f"整理失败: {result['error']}"
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

    @tool(
        "update_team_summary",
        "Update the team weekly summary (本周团队重点工作总结). Use this tool to update or create the team-level summary for a specific week. This is different from individual member reports.",
        {
            "year": int,
            "month": int,
            "week_num": int,
            "summary_content": str  # The team summary content
        }
    )
    async def update_team_summary(args: dict[str, Any]):
        """Update the team summary for a specific week."""
        year = args["year"]
        month = args["month"]
        week_num = args["week_num"]
        summary_content = args["summary_content"]

        result = report_manager.update_team_summary(
            year, month, week_num, summary_content
        )

        if result["success"]:
            return {
                "content": [{
                    "type": "text",
                    "text": result["message"]
                }]
            }
        else:
            return {
                "content": [{
                    "type": "text",
                    "text": f"更新失败: {result['error']}"
                }]
            }

    return [
        finalize_weekly_report,
        prepare_week_report_directory,
        read_weekly_report,
        read_weekly_report_bundle,
        update_weekly_report,
        generate_weekly_report,
        add_personal_summary,
        update_member_personal_summary,
        organize_weekly_report,
        read_month_report,
        list_reports,
        update_team_summary
    ]
