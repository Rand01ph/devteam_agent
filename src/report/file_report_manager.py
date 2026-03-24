"""File-based report management for directory-per-week reports."""

import json
import re
from datetime import date
from pathlib import Path
from typing import Optional


class FileReportManager:
    """Manages reports using a directory-per-week structure."""

    TEAM_SUMMARY_PLACEHOLDER = "*[待 Agent 根据各成员周报生成团队总结]*"
    AGENT_SUMMARY_PLACEHOLDER = "*[待 Agent 生成总结]*"
    WORK_DETAILS_PLACEHOLDER = "*[待生成工作明细]*"
    PERSONAL_SUMMARY_MARKERS = (
        re.compile(r"(?m)^\*\*本周工作总结\*\*[:：]?\s*$"),
    )
    AI_SUMMARY_MARKERS = (
        re.compile(r"(?m)^\*\*AI相关事项总结\*\*[:：]?\s*$"),
        re.compile(r"(?m)^\*\*AI相关\*\*[:：]?\s*$"),
        re.compile(r"(?m)^\*\*AI相关：\*\*\s*$"),
    )

    def __init__(
        self,
        reports_dir: str,
        team_members: Optional[list[str]] = None,
        team_member_name_map: Optional[dict[str, str]] = None,
    ):
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.team_members = team_members or []
        self.team_member_name_map = team_member_name_map or {}
        self.member_boundaries = self._build_member_boundaries(self.team_members, self.team_member_name_map)

    def _build_member_boundaries(
        self,
        team_members: list[str],
        team_member_name_map: dict[str, str],
    ) -> dict[str, str]:
        """Build accepted section titles mapped to target account file names."""
        boundaries: dict[str, str] = {}
        for account_name in team_members:
            boundaries[account_name] = account_name
        for display_name, account_name in team_member_name_map.items():
            boundaries[display_name] = account_name
        return boundaries

    def _get_month_dir(self, year: int, month: int) -> Path:
        return self.reports_dir / f"{year}-{month:02d}"

    def _format_date(self, d: date) -> str:
        return f"{d.month:02d}{d.day:02d}"

    def _get_week_dir_name(self, start_date: date, end_date: date) -> str:
        return f"{self._format_date(start_date)}-{self._format_date(end_date)}"

    def _find_week_dir_by_num(self, month_dir: Path, week_num: int) -> Optional[Path]:
        """Find a week directory by its week number stored in _meta.json."""
        if not month_dir.exists():
            return None

        for week_dir in month_dir.iterdir():
            if not week_dir.is_dir():
                continue
            meta_file = week_dir / "_meta.json"
            if not meta_file.exists():
                continue
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if meta.get("week_num") == week_num:
                return week_dir
        return None

    def _build_pending_template(self) -> str:
        """Build the default weekly pending report template."""
        if not self.team_members:
            return ""

        sections: list[str] = []
        for account_name in self.team_members:
            sections.append(
                "\n".join(
                    [
                        f"## {account_name}",
                        "",
                        "**本周工作总结**",
                        "",
                    ]
                )
            )

        return "\n".join(sections).rstrip() + "\n"

    def _ensure_week_support_files(self, week_dir: Path) -> None:
        """Ensure week-level helper files exist."""
        pending_file = week_dir / "_pending.md"
        if not pending_file.exists():
            pending_file.write_text(self._build_pending_template(), encoding="utf-8")

    def _ensure_week_dir(
        self,
        year: int,
        month: int,
        week_num: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Path:
        """Ensure the week directory exists and return it."""
        month_dir = self._get_month_dir(year, month)
        month_dir.mkdir(parents=True, exist_ok=True)

        week_dir = self._find_week_dir_by_num(month_dir, week_num)
        if week_dir is not None:
            self._ensure_week_support_files(week_dir)
            return week_dir

        if not start_date or not end_date:
            raise ValueError(f"Week {week_num} directory not found and no dates provided to create it.")

        week_dir = month_dir / self._get_week_dir_name(start_date, end_date)
        week_dir.mkdir(parents=True, exist_ok=True)
        meta = {
            "year": year,
            "month": month,
            "week_num": week_num,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }
        (week_dir / "_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        self._ensure_week_support_files(week_dir)
        return week_dir

    def read_report(self, year: int, month: int) -> str:
        """Read and assemble the full monthly report from directories."""
        month_dir = self._get_month_dir(year, month)
        if not month_dir.exists():
            return ""

        lines = [
            f"# {year}年{month}月团队周报\n",
            "# 本月工作总结\n\n",
        ]

        week_dirs = sorted([d for d in month_dir.iterdir() if d.is_dir()])
        for week_dir in week_dirs:
            meta_file = week_dir / "_meta.json"
            if not meta_file.exists():
                continue

            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            week_num = meta.get("week_num")
            start_str = meta.get("start_date")
            end_str = meta.get("end_date")

            if start_str and end_str:
                start_d = date.fromisoformat(start_str)
                end_d = date.fromisoformat(end_str)
                lines.append(f"# 第{week_num}周 {start_d.month}.{start_d.day}-{end_d.month}.{end_d.day}\n")
            else:
                lines.append(f"# 第{week_num}周\n")

            pending_file = week_dir / "_pending.md"
            if pending_file.exists():
                pending_content = pending_file.read_text(encoding="utf-8").strip()
                if pending_content:
                    lines.append(f"## 待整理周报\n\n{pending_content}\n")

            summary_file = week_dir / "_team_summary.md"
            if summary_file.exists():
                summary_content = summary_file.read_text(encoding="utf-8").strip()
                if summary_content:
                    lines.append(f"## 本周团队重点工作总结\n\n{summary_content}\n")

            for member_file in sorted(week_dir.glob("*.md")):
                if member_file.name.startswith("_"):
                    continue
                member_name = member_file.stem
                member_content = member_file.read_text(encoding="utf-8").strip()
                if member_content:
                    lines.append(f"## {member_name}\n\n{member_content}\n")

        return "\n".join(lines)

    def prepare_week_report_directory(
        self,
        year: int,
        month: int,
        week_num: int,
        start_date: date,
        end_date: date,
    ) -> dict:
        """Ensure a week directory exists with helper files and return details."""
        week_dir = self._ensure_week_dir(
            year,
            month,
            week_num,
            start_date=start_date,
            end_date=end_date,
        )

        pending_file = week_dir / "_pending.md"
        meta_file = week_dir / "_meta.json"
        summary_file = week_dir / "_team_summary.md"

        return {
            "success": True,
            "week_dir": str(week_dir),
            "pending_file": str(pending_file),
            "meta_file": str(meta_file),
            "summary_file": str(summary_file),
            "message": (
                f"已准备第{week_num}周周报目录: {week_dir.name}\n"
                f"- 周目录: {week_dir}\n"
                f"- 待整理输入稿: {pending_file}\n"
                f"- 元数据文件: {meta_file}\n"
                f"- 团队总结文件: {summary_file}"
            ),
        }

    def get_member_report(self, content: str, week_num: int, member_name: str) -> Optional[str]:
        """Read a member report for a specific week number."""
        del content  # Kept for backward compatibility with existing tool signatures.

        for month_dir in self.reports_dir.iterdir():
            if not month_dir.is_dir():
                continue

            week_dir = self._find_week_dir_by_num(month_dir, week_num)
            if week_dir is None:
                continue

            member_file = week_dir / f"{member_name}.md"
            if member_file.exists():
                return member_file.read_text(encoding="utf-8")

        return None

    def add_or_update_member_report(
        self,
        year: int,
        month: int,
        week_num: int,
        member_name: str,
        report_content: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> None:
        """Add or update a member's weekly report."""
        week_dir = self._ensure_week_dir(year, month, week_num, start_date=start_date, end_date=end_date)
        member_file = week_dir / f"{member_name}.md"
        content = report_content.strip()
        prefix = f"## {member_name}"
        if content.startswith(prefix):
            content = content[len(prefix):].strip()
        if member_file.exists():
            existing_content = member_file.read_text(encoding="utf-8").strip()
            content = self._merge_member_report_content(existing_content, content)
        member_file.write_text(content, encoding="utf-8")

    def _extract_section_content(self, content: str, heading: str) -> Optional[str]:
        """Extract section body from a `#### <heading>` block."""
        pattern = re.compile(rf"(?sm)^#### {re.escape(heading)}\s*\n(.*?)(?=^#### |\Z)")
        match = pattern.search(content)
        if not match:
            return None
        return match.group(1).strip()

    def _merge_member_report_content(self, existing_content: str, incoming_content: str) -> str:
        """Merge structured member report sections to avoid dropping untouched sections."""
        incoming_sections = {
            "🤖 Agent 总结": self._extract_section_content(incoming_content, "🤖 Agent 总结"),
            "个人总结": self._extract_section_content(incoming_content, "个人总结"),
            "工作明细": self._extract_section_content(incoming_content, "工作明细"),
        }
        has_structured_update = any(section is not None for section in incoming_sections.values())
        if not has_structured_update:
            return incoming_content

        existing_sections = {
            "🤖 Agent 总结": self._extract_section_content(existing_content, "🤖 Agent 总结"),
            "个人总结": self._extract_section_content(existing_content, "个人总结"),
            "工作明细": self._extract_section_content(existing_content, "工作明细"),
        }

        merged_sections: dict[str, str] = {}
        for heading, incoming_value in incoming_sections.items():
            if incoming_value is not None:
                merged_sections[heading] = incoming_value
            elif existing_sections[heading] is not None:
                merged_sections[heading] = existing_sections[heading]
            else:
                if heading == "🤖 Agent 总结":
                    merged_sections[heading] = self.AGENT_SUMMARY_PLACEHOLDER
                elif heading == "工作明细":
                    merged_sections[heading] = self.WORK_DETAILS_PLACEHOLDER
                else:
                    merged_sections[heading] = ""

        return (
            "### 本周工作总结\n\n"
            f"#### 🤖 Agent 总结\n\n{merged_sections['🤖 Agent 总结']}\n\n"
            f"#### 个人总结\n\n{merged_sections['个人总结']}\n\n"
            f"#### 工作明细\n\n{merged_sections['工作明细']}"
        ).strip()

    def _unwrap_markdown_code_block(self, content: str) -> str:
        """Extract content from a wrapped markdown code block if present."""
        code_block_match = re.search(r"```(?:markdown)?\s*\n(.*?)```", content, re.DOTALL)
        if code_block_match:
            return code_block_match.group(1)
        return content

    def _looks_like_unknown_member_title(self, title: str) -> bool:
        """Identify plain second-level headings that look like unknown member names."""
        if not title:
            return False
        if title in self.member_boundaries:
            return False
        if title in {"待整理周报", "本周团队重点工作总结"}:
            return False
        if re.match(r"^\d+[\.\)]", title):
            return False
        if any(marker in title for marker in ("*", "`", "[", "]")):
            return False
        return True

    def _extract_member_blocks(self, pending_content: str) -> tuple[list[tuple[str, str, str]], list[str]]:
        """Split pending content into known member blocks and skipped unknown members."""
        content = self._unwrap_markdown_code_block(pending_content)
        header_matches = list(re.finditer(r"(?m)^##\s+(.+?)\s*$", content))
        boundaries: list[tuple[int, int, str, bool]] = []

        for match in header_matches:
            title = match.group(1).strip()
            if title in self.member_boundaries:
                boundaries.append((match.start(), match.end(), title, True))
            elif self._looks_like_unknown_member_title(title):
                boundaries.append((match.start(), match.end(), title, False))

        if not boundaries:
            return [], []

        members_data: list[tuple[str, str, str]] = []
        skipped_unknown: list[str] = []

        for index, (_, header_end, display_name, is_known) in enumerate(boundaries):
            next_start = boundaries[index + 1][0] if index + 1 < len(boundaries) else len(content)
            raw_member_content = content[header_end:next_start].strip()
            if is_known:
                account_name = self.member_boundaries[display_name]
                members_data.append((display_name, account_name, raw_member_content))
            elif display_name not in skipped_unknown:
                skipped_unknown.append(display_name)

        return members_data, skipped_unknown

    def _find_first_marker(
        self,
        content: str,
        markers: tuple[re.Pattern[str], ...],
        start_pos: int = 0,
    ) -> Optional[re.Match[str]]:
        """Find the earliest marker match after start_pos."""
        matches = [marker.search(content, start_pos) for marker in markers]
        valid_matches = [match for match in matches if match is not None]
        if not valid_matches:
            return None
        return min(valid_matches, key=lambda match: match.start())

    def _extract_personal_summary(self, raw_member_content: str) -> str:
        """Extract the personal summary content from a raw pending member block."""
        content = raw_member_content.strip()
        if not content:
            return ""

        work_match = self._find_first_marker(content, self.PERSONAL_SUMMARY_MARKERS)
        work_start = work_match.end() if work_match else 0
        ai_match = self._find_first_marker(content, self.AI_SUMMARY_MARKERS, start_pos=work_start)

        if work_match:
            main_content = content[work_start:ai_match.start() if ai_match else len(content)].strip()
        else:
            main_content = content[:ai_match.start() if ai_match else len(content)].strip()

        ai_content = content[ai_match.end():].strip() if ai_match else ""

        parts: list[str] = []
        if main_content:
            parts.append(main_content)
        if ai_content:
            ai_summary = f"AI相关事项总结：\n{ai_content}"
            parts.append(ai_summary)

        combined = "\n\n".join(part for part in parts if part).strip()
        return combined or content

    def _build_structured_member_content(self, personal_summary: str) -> str:
        """Build the standard member report structure."""
        return (
            "### 本周工作总结\n\n"
            f"#### 🤖 Agent 总结\n\n{self.AGENT_SUMMARY_PLACEHOLDER}\n\n"
            f"#### 个人总结\n\n{personal_summary}\n\n"
            f"#### 工作明细\n\n{self.WORK_DETAILS_PLACEHOLDER}"
        )

    def _replace_personal_summary_section(self, existing_content: str, personal_summary: str) -> str:
        """Replace or insert the personal summary section while preserving other sections."""
        replacement = f"#### 个人总结\n\n{personal_summary}\n"

        pattern_before_work_details = re.compile(
            r"(?s)#### 个人总结\s*.*?(?=\n#### 工作明细\b)"
        )
        if pattern_before_work_details.search(existing_content):
            return pattern_before_work_details.sub(replacement.rstrip(), existing_content, count=1)

        pattern_to_next_heading = re.compile(
            r"(?s)#### 个人总结\s*.*?(?=\n#### |\Z)"
        )
        if pattern_to_next_heading.search(existing_content):
            return pattern_to_next_heading.sub(replacement.rstrip(), existing_content, count=1)

        work_details_pattern = re.compile(r"(?m)^#### 工作明细\b")
        if work_details_pattern.search(existing_content):
            return work_details_pattern.sub(f"{replacement}\n#### 工作明细", existing_content, count=1)

        return existing_content.rstrip() + f"\n\n{replacement.rstrip()}\n"

    def organize_week_content(
        self,
        year: int,
        month: int,
        week_num: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> dict:
        """Organize raw content in _pending.md into member report files."""
        try:
            week_dir = self._ensure_week_dir(
                year,
                month,
                week_num,
                start_date=start_date,
                end_date=end_date,
            )
        except ValueError as exc:
            return {"success": False, "error": str(exc)}

        pending_file = week_dir / "_pending.md"
        if not pending_file.exists():
            return {"success": False, "error": "未找到待整理内容 (_pending.md)"}

        pending_content = pending_file.read_text(encoding="utf-8")
        if not pending_content.strip():
            return {"success": False, "error": "待整理内容为空"}

        members_data, skipped_unknown = self._extract_member_blocks(pending_content)
        if not members_data:
            if skipped_unknown:
                return {
                    "success": False,
                    "error": (
                        "未找到任何已配置成员的周报内容。"
                        f" 已跳过未知成员: {', '.join(skipped_unknown)}"
                    ),
                }
            return {"success": False, "error": "未找到任何成员内容格式(## 成员名)"}

        members_found: list[str] = []
        members_written: list[str] = []

        for display_name, account_name, raw_content in members_data:
            personal_summary = self._extract_personal_summary(raw_content)
            member_file = week_dir / f"{account_name}.md"
            if member_file.exists():
                existing_content = member_file.read_text(encoding="utf-8").strip()
                updated_content = self._replace_personal_summary_section(existing_content, personal_summary)
            else:
                updated_content = self._build_structured_member_content(personal_summary)
            member_file.write_text(updated_content.strip() + "\n", encoding="utf-8")
            members_found.append(display_name)
            members_written.append(account_name)

        pending_file.write_text("", encoding="utf-8")

        team_summary_file = week_dir / "_team_summary.md"
        if not team_summary_file.exists() or not team_summary_file.read_text(encoding="utf-8").strip():
            team_summary_file.write_text(self.TEAM_SUMMARY_PLACEHOLDER, encoding="utf-8")

        message = f"已整理 {len(members_found)} 位成员的周报: {', '.join(members_found)}"
        if skipped_unknown:
            message += f"\n已跳过未知成员: {', '.join(skipped_unknown)}"

        return {
            "success": True,
            "members_organized": members_found,
            "members_written": members_written,
            "unknown_members_skipped": skipped_unknown,
            "message": message,
        }

    def list_reports(self) -> list[tuple[int, int]]:
        """List all available reports."""
        reports = []
        for directory in self.reports_dir.iterdir():
            if not directory.is_dir():
                continue
            match = re.match(r"(\d{4})-(\d{2})", directory.name)
            if match:
                year, month = int(match.group(1)), int(match.group(2))
                reports.append((year, month))
        return sorted(reports)

    def update_team_summary(
        self,
        year: int,
        month: int,
        week_num: int,
        summary_content: str,
    ) -> dict:
        """Update the team summary for a specific week."""
        month_dir = self._get_month_dir(year, month)
        week_dir = self._find_week_dir_by_num(month_dir, week_num)

        if not week_dir:
            return {"success": False, "error": f"Week {week_num} directory not found"}

        summary_file = week_dir / "_team_summary.md"
        content = summary_content.strip()
        prefix = "## 本周团队重点工作总结"
        if content.startswith(prefix):
            content = content[len(prefix):].strip()

        summary_file.write_text(content, encoding="utf-8")
        return {"success": True, "message": f"已更新第{week_num}周的团队工作总结"}
