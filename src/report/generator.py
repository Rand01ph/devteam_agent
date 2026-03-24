"""Weekly report generator."""

import re
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Optional
from ..integrations.gitlab_client import GitLabClient
from ..integrations.jira_client import JiraClient


class ReportGenerator:
    """Generates weekly reports from GitLab and Jira data."""

    AGENT_SUMMARY_PLACEHOLDER = "*[待 Agent 根据以下工作明细生成总结]*"
    LEGACY_AGENT_SUMMARY_PLACEHOLDER = "*[待 Agent 生成总结]*"
    PERSONAL_SUMMARY_PLACEHOLDER = "*[待成员填写个人总结]*"
    WORK_DETAILS_PLACEHOLDER = "*[待生成工作明细]*"
    MEMBER_SUMMARY_SUBAGENT_NAME = "member-personal-summarizer"
    MEMBER_SUMMARY_SUBAGENT_DESCRIPTION = (
        "擅长将成员原始周报整理为简洁、正式、结果导向的个人总结。"
        "当需要生成或润色成员个人总结时使用。"
    )
    MEMBER_SUMMARY_PARENT_PROMPT = (
        "你负责协调成员个人总结生成任务。"
        f"必须使用 `{MEMBER_SUMMARY_SUBAGENT_NAME}` 子代理完成整理，"
        "不要自己直接撰写。最终只返回子代理产出的个人总结正文。"
    )
    MEMBER_SUMMARY_SYSTEM_PROMPT = """# Role
你是一名专业的研发团队周报助手。你的任务是将某位成员本周零散、口语化或条目式的工作内容，整理成一段适合写入 `#### 个人总结` 的正式总结。

# Goal
输出一段 2-4 句的中文个人总结，突出：
- 本周主要推进的工作
- 关键进展或阶段结果（如完成、上线、提测、灰度、验证中）
- 需要保留的 AI 相关事项（如果与本周工作相关）

# Rules
1. 输出必须简洁、连贯、正式，不要使用列表。
2. 不要出现 Jira、MR、评论数等细节统计，除非该数字本身非常关键。
3. 可以保留重要状态词：已完成、已上线、已提测、灰度中、待验证、推进中。
4. 去掉低价值噪音，如请假、泛泛学习记录、零碎会议。
5. 如果输入中包含 AI相关事项总结，只有在确实构成本周重点时才融入总结。
6. 不要编造内容，不要输出标题，不要加引号，不要加“以下是总结”。

# Output
仅输出个人总结正文。
"""
    TEAM_SUMMARY_SUBAGENT_NAME = "team-weekly-summarizer"
    TEAM_SUMMARY_SUBAGENT_DESCRIPTION = (
        "擅长将多位研发成员周报重组为面向管理层的团队级周报。"
        "当需要生成团队周报总结、提炼重点工作、输出成员概览/亮点/待关注时使用。"
    )
    TEAM_SUMMARY_PARENT_PROMPT = (
        "你负责协调团队周报总结任务。"
        f"必须使用 `{TEAM_SUMMARY_SUBAGENT_NAME}` 子代理完成分析和写作，"
        "不要自己直接总结。"
        "最终只返回子代理生成的最终 Markdown，不要添加任何额外说明。"
    )
    TEAM_SUMMARY_SYSTEM_PROMPT = """# Role
你是一名研发团队技术经理 / 项目经理。你的任务不是复述成员周报，而是把多个成员的周报内容整合成一份适合向管理层汇报的团队级周报。

# Goal
输出一份结构化、结果导向、业务导向的团队周报，突出：
- 本周核心项目进展
- 已完成、已提测、已上线、灰度中的关键事项
- 重要问题修复与支撑事项
- 团队级协作、运维和管理动作
- AI 转型相关的研发实践与资源推进

# Core Rules
1. 不要按成员流水账复述，不要写“某某做了什么”。
2. 必须按项目 / 业务模块 / 职能域重组内容；多人参与同一事项时合并为团队级描述。
3. 优先使用“完成、推进、修复、优化、上线、发布、提测、验证、支撑、协调”等结果导向动词。
4. 去掉低价值噪音：纯学习、请假、零散沟通、MR/Jira 明细、评论数量、工时明细本身。
5. 保留关键量化信息：百分比、预算、token 消耗、灰度/全量发布、100人限制等。
6. AI 功能开发归入“重点开发及维护进展”；AI 预算、模型成本、试点推进、能力建设归入“团队管理 (AI 转型实践)”。

# Output Format
严格输出 Markdown，结构如下：

# {时间范围}

## 本周重点工作记录

### 重点开发及维护进展
- 按项目或子系统分组，例如 `【Portal 平台】`、`【Idun 流水线】`、`【DevMarket / AI 平台】`、`【Ceres / 效能度量】`
- 每个分组下保留最有价值的 1-3 条结果型描述

### 组织级配置管理
- 仅保留配置审查、门禁、权限、发布管理、审计等组织级动作

### 产研公共事项支持
- 保留安全漏洞、生产支撑、预算协同、外部支撑、公共平台问题处理等事项

### 横向沟通及汇报
- 保留跨团队会议、方案推进、试点协同、管理沟通、专项汇报等

### 运维工作
- 保留系统升级、证书更新、环境维护、联调、故障排查等

### 团队管理 (AI 转型实践)
- 保留招聘、培训、团队能力建设，以及 AI 转型相关的文化、方法、基建、预算和资源动作

---

### 👥 成员工作概览
- 使用 Markdown 表格，列为：成员、主要工作、工时、MR数
- 主要工作使用简短概括，保留已有统计信息

---

### ✅ 本周亮点
- 输出 3-4 条最值得向管理层汇报的结果

### ⚠️ 待关注
- 输出 1-3 条需要跟踪的问题、风险或资源事项
- 如果没有明确风险，不要编造

# Quality Bar
- 管理层一眼能看懂团队这周做成了什么
- 不是按成员罗列，而是按业务模块整合
- 风格接近正式周报，而不是聊天摘要
- 不要输出“以下是总结”之类多余前缀
"""

    def __init__(
        self,
        gitlab_client: GitLabClient,
        jira_client: JiraClient,
        claude_env: Optional[dict[str, str]] = None,
        claude_model: Optional[str] = None,
        cwd: Optional[str] = None,
    ):
        """
        Initialize report generator.

        Args:
            gitlab_client: GitLab client instance
            jira_client: Jira client instance
        """
        self.gitlab = gitlab_client
        self.jira = jira_client
        self.claude_env = claude_env or {}
        self.claude_model = claude_model
        self.cwd = str(cwd or Path.cwd())

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

        # Format report with new structure
        report_lines = []

        # Section header
        report_lines.append("### 本周工作总结\n")

        # Agent summary placeholder (will be filled by Agent)
        report_lines.append("#### 🤖 Agent 总结\n")
        report_lines.append("*[待 Agent 根据以下工作明细生成总结]*\n")

        # Personal summary placeholder (will be filled by team member)
        report_lines.append("#### 个人总结\n")
        report_lines.append("*[待成员填写个人总结]*\n")

        # Work details section
        report_lines.append("#### 工作明细\n")

        has_content = False

        # GitLab Push Events (代码提交)
        if gitlab_activity["summary"]["total_pushes"] > 0:
            has_content = True
            total_commits = gitlab_activity["summary"]["total_commits"]
            total_pushes = gitlab_activity["summary"]["total_pushes"]
            report_lines.append(f"**代码推送**: {total_pushes} 次推送 (共 {total_commits} 次提交)")

            for push in gitlab_activity["push_events"]:
                commit_count = push.get("commit_count", 1)
                ref = push.get("ref", "unknown")
                commit_title = push.get("commit_title", "")
                report_lines.append(f"  - 推送 {commit_count} 个提交到 `{ref}`: {commit_title}")

            report_lines.append("")

        # GitLab MR Events (合并请求)
        if gitlab_activity["summary"]["total_merge_requests"] > 0:
            has_content = True
            report_lines.append(f"**合并请求活动**: {gitlab_activity['summary']['total_merge_requests']} 个 MR 相关事件")

            for mr in gitlab_activity["merge_request_events"]:
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

            for issue in gitlab_activity["issue_events"]:
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

            for comment in gitlab_activity["comment_events"]:
                noteable_type = comment.get("noteable_type", "")
                note_body = comment.get("note_body", "")[:80]
                suffix = "..." if len(comment.get("note_body", "")) > 80 else ""
                report_lines.append(f"  - 在 {noteable_type} 上评论: {note_body}{suffix}")

            report_lines.append("")

        # Jira Worklogs (工时统计)
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

            for issue_key, data in sorted_issues:
                hours = data["total_seconds"] // 3600
                minutes = (data["total_seconds"] % 3600) // 60
                time_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
                report_lines.append(f"  - [{issue_key}]({self.jira.url}/browse/{issue_key}) **{time_str}**: {data['summary']}")

            report_lines.append("")

        # Jira Issues section
        if jira_summary["total_assigned"] > 0 or jira_summary["total_reported"] > 0:
            has_content = True
            report_lines.append(f"**Jira Issues**: 分配 {jira_summary['total_assigned']} 个, 创建 {jira_summary['total_reported']} 个")

            for issue in jira_activity["all_issues"]:
                issue_type = issue.get("type") or ""
                status = issue.get("status") or "N/A"
                type_emoji = self._get_issue_type_emoji(issue_type)
                status_emoji = "✅" if status.lower() in ["done", "closed", "resolved"] else "🔄"
                report_lines.append(f"  - {type_emoji} {status_emoji} [{issue['key']}]({issue['url']}) {issue['summary']}")

            report_lines.append("")

        # If no activity
        if not has_content:
            report_lines.append("本周暂无记录的活动。\n")

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
        member_reports: dict[str, str],
        week_label: Optional[str] = None,
    ) -> str:
        """
        Generate a summary of the entire team's weekly work.

        Args:
            member_reports: Member report contents keyed by account name

        Returns:
            Summary text in markdown
        """
        if not member_reports:
            return "本周暂无可汇总的成员周报。"

        try:
            return await self._generate_team_summary_with_llm(member_reports, week_label)
        except Exception:
            return self._generate_team_weekly_summary_fallback(member_reports, week_label)

    async def generate_member_personal_summary(
        self,
        member_name: str,
        report_content: str,
        week_label: Optional[str] = None,
    ) -> str:
        """Generate a concise personal summary for one member."""
        personal_summary = self._extract_section_content(report_content, "个人总结")
        work_details = self._extract_section_content(report_content, "工作明细")
        agent_summary = self._extract_section_content(report_content, "🤖 Agent 总结")

        fallback = self._fallback_member_personal_summary(personal_summary, work_details, agent_summary)

        prompt = (
            f"成员: {member_name}\n"
            f"时间范围: {week_label or '本周'}\n\n"
            f"当前个人总结：\n{personal_summary or '-'}\n\n"
            f"当前 Agent 总结：\n{agent_summary or '-'}\n\n"
            f"工作明细：\n{work_details or '-'}"
        )

        try:
            content = await self._run_subagent(
                subagent_name=self.MEMBER_SUMMARY_SUBAGENT_NAME,
                subagent_description=self.MEMBER_SUMMARY_SUBAGENT_DESCRIPTION,
                subagent_prompt=self.MEMBER_SUMMARY_SYSTEM_PROMPT,
                parent_prompt=self.MEMBER_SUMMARY_PARENT_PROMPT,
                user_prompt=(
                    f"使用 `{self.MEMBER_SUMMARY_SUBAGENT_NAME}` 子代理生成该成员的个人总结。\n\n{prompt}"
                ),
            )
            return content or fallback
        except Exception:
            return fallback

    def needs_generated_personal_summary(self, report_content: str) -> bool:
        """Return True when a member report still needs an LLM personal summary."""
        personal_summary = self._extract_section_content(report_content, "个人总结")
        return self._is_placeholder(personal_summary)

    def _generate_team_weekly_summary_fallback(
        self,
        member_reports: dict[str, str],
        week_label: Optional[str],
    ) -> str:
        """Fallback summary generator used when the LLM path is unavailable."""
        focus_map: dict[str, set[str]] = defaultdict(set)
        member_highlights: list[str] = []

        for member_name, report_content in member_reports.items():
            agent_summary = self._extract_section_content(report_content, "🤖 Agent 总结")
            personal_summary = self._extract_section_content(report_content, "个人总结")
            work_details = self._extract_section_content(report_content, "工作明细")

            primary_summary = self._choose_member_summary(agent_summary, personal_summary)
            if primary_summary:
                member_highlights.append(f"{member_name}：{primary_summary}")

            focus_terms = self._extract_focus_terms(agent_summary, personal_summary, work_details)
            for term in focus_terms:
                focus_map[term].add(member_name)

        lines: list[str] = [f"# {week_label or '本周'}", "", "## 本周重点工作记录", ""]

        ranked_focus = sorted(
            focus_map.items(),
            key=lambda item: (-len(item[1]), item[0]),
        )

        lines.append("### 重点开发及维护进展")
        if ranked_focus:
            for index, (term, members) in enumerate(ranked_focus[:5], start=1):
                member_list = "、".join(sorted(members))
                lines.append(f"- **{term}**：由 {member_list} 重点推进。")
        else:
            summary = "；".join(member_highlights[:4]) if member_highlights else "本周已完成成员周报整理。"
            lines.append(f"- **团队整体推进稳定**：{summary}")

        collaboration_terms = [term for term, members in ranked_focus if len(members) > 1][:3]
        if collaboration_terms:
            lines.append("")
            lines.append("### 横向沟通及汇报")
            lines.append(f"- 团队协作方面，围绕 {'、'.join(collaboration_terms)} 形成了跨成员协同推进。")

        if member_highlights:
            lines.append("")
            lines.append("---")
            lines.append("")
            lines.append("### ✅ 本周亮点")
            for highlight in member_highlights[:5]:
                lines.append(f"- {highlight}")

        return "\n".join(lines).strip()

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

    def _extract_section_content(self, content: str, heading: str) -> str:
        """Extract the body of a structured report section."""
        pattern = re.compile(rf"(?sm)^#### {re.escape(heading)}\s*\n(.*?)(?=^#### |\Z)")
        match = pattern.search(content)
        if not match:
            return ""
        return match.group(1).strip()

    def _is_placeholder(self, value: str) -> bool:
        """Return True when a section only contains a placeholder."""
        normalized = value.strip()
        return normalized in {
            "",
            self.AGENT_SUMMARY_PLACEHOLDER,
            self.LEGACY_AGENT_SUMMARY_PLACEHOLDER,
            self.PERSONAL_SUMMARY_PLACEHOLDER,
            self.WORK_DETAILS_PLACEHOLDER,
        }

    def _clean_summary_text(self, value: str) -> str:
        """Normalize markdown-heavy summary text into a short sentence."""
        text = value.strip()
        if self._is_placeholder(text):
            return ""

        text = re.sub(r"`([^`]+)`", r"\1", text)
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
        text = re.sub(r"\s+", " ", text).strip(" -")
        if not text:
            return ""

        sentences = re.split(r"(?<=[。！？;；])\s+", text)
        summary = sentences[0].strip()
        return summary[:120].rstrip("，,；;")

    def _choose_member_summary(self, agent_summary: str, personal_summary: str) -> str:
        """Choose the most useful summary for the member."""
        cleaned_agent = self._clean_summary_text(agent_summary)
        if cleaned_agent:
            return cleaned_agent

        cleaned_personal = self._clean_summary_text(personal_summary)
        if cleaned_personal:
            return cleaned_personal

        return ""

    def _extract_focus_terms(self, agent_summary: str, personal_summary: str, work_details: str) -> list[str]:
        """Extract a few focus terms from summaries and work details."""
        candidates: list[str] = []
        primary_summary = self._choose_member_summary(agent_summary, personal_summary)
        combined = "\n".join(part for part in (agent_summary, personal_summary, work_details) if part).strip()
        if not combined:
            return candidates

        for term in re.findall(r"\*\*([^*\n]{2,40})\*\*", combined):
            normalized = self._normalize_focus_term(term)
            if normalized:
                candidates.append(normalized)

        for match in re.finditer(r"(?m)^\*\*([^*\n:：]{2,40})\*\*[:：]", work_details or ""):
            normalized = self._normalize_focus_term(match.group(1))
            if normalized:
                candidates.append(normalized)

        if not candidates and primary_summary:
            segments = re.split(r"[，,；;。]", primary_summary)
            for segment in segments:
                normalized = self._normalize_focus_term(segment)
                if normalized:
                    candidates.append(normalized)
                if len(candidates) >= 3:
                    break

        deduped: list[str] = []
        for candidate in candidates:
            if candidate not in deduped:
                deduped.append(candidate)
        return deduped[:3]

    def _normalize_focus_term(self, value: str) -> str:
        """Normalize a focus term and filter out generic content."""
        term = value.strip()
        term = re.sub(r"\s+", " ", term)
        term = term.strip("：:，,。.;；- ")
        if len(term) < 2 or len(term) > 28:
            return ""

        generic_terms = {
            "Jira 工时",
            "Jira Issues",
            "评论活动",
            "合并请求活动",
            "GitLab Issue 活动",
            "代码推送",
            "本周工作总结",
            "团队整体推进稳定",
        }
        if term in generic_terms:
            return ""
        if re.fullmatch(r"\d+h(?: \d+m)?", term):
            return ""
        if re.fullmatch(r"[A-Z]+-\d+", term):
            return ""
        if any(
            token in term for token in (
                "累计投入",
                "投入工时",
                "小时工时",
                "提交了",
                "分配了",
                "发表了",
                "主要完成了",
                "当前负责",
                "同时被分配",
                "其中",
            )
        ):
            return ""
        if term.startswith("AI相关事项总结"):
            return "AI相关事项"
        return term

    async def _generate_team_summary_with_llm(
        self,
        member_reports: dict[str, str],
        week_label: Optional[str],
    ) -> str:
        """Generate a polished team summary with Claude subagent flow."""
        overview_rows = self._build_member_overview_rows(member_reports)
        overview_text = "\n".join(
            f"- {row['member']} | 主要工作: {row['main_work']} | 工时: {row['hours']} | MR数: {row['mr_count']}"
            for row in overview_rows
        )

        report_blocks: list[str] = []
        for member_name, report_content in member_reports.items():
            report_blocks.append(f"## {member_name}\n{report_content.strip()}")

        prompt = (
            f"时间范围: {week_label or '本周'}\n\n"
            "成员统计信息：\n"
            f"{overview_text}\n\n"
            "成员周报原文如下：\n\n"
            f"{chr(10).join(report_blocks)}"
        )

        return await self._run_subagent(
            subagent_name=self.TEAM_SUMMARY_SUBAGENT_NAME,
            subagent_description=self.TEAM_SUMMARY_SUBAGENT_DESCRIPTION,
            subagent_prompt=self.TEAM_SUMMARY_SYSTEM_PROMPT,
            parent_prompt=self.TEAM_SUMMARY_PARENT_PROMPT,
            user_prompt=f"使用 `{self.TEAM_SUMMARY_SUBAGENT_NAME}` 子代理完成团队周报总结。\n\n{prompt}",
        )

    def _build_member_overview_rows(self, member_reports: dict[str, str]) -> list[dict[str, str]]:
        """Build member overview rows for the team summary prompt."""
        rows: list[dict[str, str]] = []
        for member_name, report_content in member_reports.items():
            agent_summary = self._extract_section_content(report_content, "🤖 Agent 总结")
            personal_summary = self._extract_section_content(report_content, "个人总结")
            work_details = self._extract_section_content(report_content, "工作明细")

            rows.append({
                "member": member_name,
                "main_work": self._extract_member_main_work(agent_summary, personal_summary, work_details),
                "hours": self._extract_member_hours(report_content),
                "mr_count": self._extract_member_mr_count(work_details),
            })
        return rows

    def _extract_member_main_work(self, agent_summary: str, personal_summary: str, work_details: str) -> str:
        """Extract a short main-work label for the member overview table."""
        terms = self._extract_focus_terms(agent_summary, personal_summary, work_details)
        if terms:
            return "、".join(terms[:3])

        primary_summary = self._choose_member_summary(agent_summary, personal_summary)
        if not primary_summary:
            return "-"

        shortened = primary_summary[:32].rstrip("，,；;。")
        return shortened or "-"

    def _extract_member_hours(self, report_content: str) -> str:
        """Extract the Jira worklog summary shown in the member report."""
        match = re.search(r"\*\*Jira 工时\*\*:\s*([^\n]+)", report_content)
        if not match:
            return "-"
        return match.group(1).strip()

    def _extract_member_mr_count(self, work_details: str) -> str:
        """Extract new MR count when present; otherwise return '-'."""
        opened_matches = re.findall(r"(?m)^\s*-\s*🆕\s+(?:opened|created)\s+MR\b", work_details)
        if opened_matches:
            return f"{len(opened_matches)}个新开"

        total_match = re.search(r"\*\*合并请求活动\*\*:\s*(\d+)\s*个", work_details)
        if total_match:
            return f"{total_match.group(1)}个相关"

        return "-"

    def _fallback_member_personal_summary(
        self,
        personal_summary: str,
        work_details: str,
        agent_summary: str,
    ) -> str:
        """Fallback personal summary when the LLM path is unavailable."""
        cleaned_personal = self._clean_summary_text(personal_summary)
        if cleaned_personal:
            return cleaned_personal

        cleaned_agent = self._clean_summary_text(agent_summary)
        if cleaned_agent:
            return cleaned_agent

        focus_terms = self._extract_focus_terms(agent_summary, personal_summary, work_details)
        if focus_terms:
            return f"本周主要推进{'、'.join(focus_terms[:3])}相关工作，并持续跟进对应事项的落地与验证。"

        return "本周持续推进既定工作，并完成相关事项的跟进与整理。"

    async def _run_subagent(
        self,
        *,
        subagent_name: str,
        subagent_description: str,
        subagent_prompt: str,
        parent_prompt: str,
        user_prompt: str,
    ) -> str:
        """Run a single-purpose subagent and return its text output."""
        from claude_agent_sdk import (
            AgentDefinition,
            AssistantMessage,
            ClaudeAgentOptions,
            ClaudeSDKClient,
            TextBlock,
        )

        options = ClaudeAgentOptions(
            allowed_tools=["Task"],
            system_prompt=parent_prompt,
            permission_mode="default",
            model=self.claude_model,
            env=self.claude_env,
            cwd=self.cwd,
            setting_sources=["project"],
            max_turns=1,
            agents={
                subagent_name: AgentDefinition(
                    description=subagent_description,
                    prompt=subagent_prompt,
                    tools=[],
                    model="inherit",
                )
            },
        )

        client = ClaudeSDKClient(options)
        await client.connect()
        try:
            await client.query(user_prompt)
            response_text = ""
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            response_text += block.text
            content = response_text.strip()
            if not content:
                raise ValueError("Claude did not return text")
            return content
        finally:
            await client.disconnect()
