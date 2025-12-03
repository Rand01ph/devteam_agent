"""Markdown weekly report file management."""

import re
from datetime import datetime, date
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class MarkdownSection:
    """Represents a markdown section with a heading."""
    level: int  # Heading level (1-6)
    title: str  # Heading text (without #)
    content: str = ""  # Content after heading, before next heading
    children: list["MarkdownSection"] = field(default_factory=list)


class MarkdownReportManager:
    """Manages markdown weekly report files organized by month."""

    def __init__(self, reports_dir: str):
        """
        Initialize the report manager.

        Args:
            reports_dir: Directory to store report files
        """
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def get_report_file_path(self, year: int, month: int) -> Path:
        """Get the report file path for a specific year and month."""
        return self.reports_dir / f"{year}-{month:02d}.md"

    def get_current_report_file_path(self) -> Path:
        """Get the report file path for current month."""
        now = datetime.now()
        return self.get_report_file_path(now.year, now.month)

    def ensure_report_file_exists(self, year: int, month: int) -> Path:
        """Ensure report file exists for the specified month, create if not."""
        file_path = self.get_report_file_path(year, month)
        if not file_path.exists():
            # Create initial file with title and month summary section
            file_path.write_text(
                f"# {year}年{month}月团队周报\n\n"
                f"# 本月工作总结\n\n",
                encoding="utf-8"
            )
        return file_path

    def read_report(self, year: int, month: int) -> str:
        """Read report content for a specific month."""
        file_path = self.get_report_file_path(year, month)
        if not file_path.exists():
            return ""
        return file_path.read_text(encoding="utf-8")

    def parse_markdown(self, content: str) -> list[MarkdownSection]:
        """
        Parse markdown content into a list of sections.
        Only parses top-level structure (# headings).
        """
        sections = []
        lines = content.split("\n")
        current_section = None
        content_lines = []

        for line in lines:
            # Check if it's a heading
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if heading_match:
                # Save previous section
                if current_section is not None:
                    current_section.content = "\n".join(content_lines).strip()
                    sections.append(current_section)
                    content_lines = []

                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                current_section = MarkdownSection(level=level, title=title)
            else:
                content_lines.append(line)

        # Don't forget the last section
        if current_section is not None:
            current_section.content = "\n".join(content_lines).strip()
            sections.append(current_section)

        return sections

    def sections_to_markdown(self, sections: list[MarkdownSection]) -> str:
        """Convert sections back to markdown text."""
        lines = []
        for section in sections:
            heading = "#" * section.level + " " + section.title
            lines.append(heading)
            if section.content:
                lines.append("")
                lines.append(section.content)
            lines.append("")
        return "\n".join(lines)

    def get_week_section(self, content: str, week_num: int) -> Optional[str]:
        """
        Extract a specific week section from report content.
        """
        sections = self.parse_markdown(content)

        # Find the week section
        week_pattern = rf"^第{week_num}周(?:\s+\d+\.\d+-\d+\.\d+)?$"
        week_start_idx = None
        week_end_idx = None

        for i, section in enumerate(sections):
            if section.level == 1 and re.match(week_pattern, section.title):
                week_start_idx = i
                # Find the end (next level-1 heading or end)
                for j in range(i + 1, len(sections)):
                    if sections[j].level == 1:
                        week_end_idx = j
                        break
                if week_end_idx is None:
                    week_end_idx = len(sections)
                break

        if week_start_idx is None:
            return None

        # Rebuild the week section content
        week_sections = sections[week_start_idx:week_end_idx]
        return self.sections_to_markdown(week_sections)

    def get_member_report(self, content: str, week_num: int, member_name: str) -> Optional[str]:
        """
        Extract a specific member's report for a specific week.
        """
        week_content = self.get_week_section(content, week_num)
        if not week_content:
            return None

        sections = self.parse_markdown(week_content)

        # Find member section (## member_name)
        member_start_idx = None
        member_end_idx = None

        for i, section in enumerate(sections):
            if section.level == 2 and section.title == member_name:
                member_start_idx = i
                # Find the end (next level-2 heading or end)
                for j in range(i + 1, len(sections)):
                    if sections[j].level <= 2:
                        member_end_idx = j
                        break
                if member_end_idx is None:
                    member_end_idx = len(sections)
                break

        if member_start_idx is None:
            return None

        member_sections = sections[member_start_idx:member_end_idx]
        return self.sections_to_markdown(member_sections)

    def add_or_update_member_report(
        self,
        year: int,
        month: int,
        week_num: int,
        member_name: str,
        report_content: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> None:
        """
        Add or update a member's weekly report.
        """
        file_path = self.ensure_report_file_exists(year, month)
        content = file_path.read_text(encoding="utf-8")
        sections = self.parse_markdown(content)

        # Build week header
        if start_date and end_date:
            week_title = f"第{week_num}周 {start_date.month}.{start_date.day}-{end_date.month}.{end_date.day}"
        else:
            week_title = f"第{week_num}周"

        # Find or create week section
        week_pattern = rf"^第{week_num}周(?:\s+\d+\.\d+-\d+\.\d+)?$"
        week_idx = None
        for i, section in enumerate(sections):
            if section.level == 1 and re.match(week_pattern, section.title):
                week_idx = i
                break

        if week_idx is None:
            # Create new week section at the end
            week_section = MarkdownSection(level=1, title=week_title, content="")
            team_summary = MarkdownSection(level=2, title="本周团队重点工作总结", content="")
            sections.append(week_section)
            sections.append(team_summary)
            week_idx = len(sections) - 2

        # Find the range of this week (from week_idx to next level-1 or end)
        week_end_idx = len(sections)
        for i in range(week_idx + 1, len(sections)):
            if sections[i].level == 1:
                week_end_idx = i
                break

        # Find if member already exists in this week
        member_idx = None
        member_end_idx = None
        for i in range(week_idx + 1, week_end_idx):
            if sections[i].level == 2 and sections[i].title == member_name:
                member_idx = i
                # Find end of member section
                for j in range(i + 1, week_end_idx):
                    if sections[j].level <= 2:
                        member_end_idx = j
                        break
                if member_end_idx is None:
                    member_end_idx = week_end_idx
                break

        # Parse the new report content into sections
        new_member_sections = self.parse_markdown(f"## {member_name}\n\n{report_content}")

        if member_idx is not None:
            # Replace existing member section
            sections = sections[:member_idx] + new_member_sections + sections[member_end_idx:]
        else:
            # Insert new member section at the end of the week (before next week)
            sections = sections[:week_end_idx] + new_member_sections + sections[week_end_idx:]

        # Write back
        new_content = self.sections_to_markdown(sections)
        file_path.write_text(new_content, encoding="utf-8")

    def organize_week_content(
        self,
        year: int,
        month: int,
        week_num: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> dict:
        """
        Organize the raw content in "待整理周报" section into proper member structures.

        Workflow:
        1. Find the week section
        2. Find "## 待整理周报" subsection
        3. Parse member content from it (## 成员名 format)
        4. Create proper structure for each member
        5. Clear the "待整理周报" section

        Returns a dict with organized members and any issues found.
        """
        file_path = self.get_report_file_path(year, month)
        if not file_path.exists():
            return {"success": False, "error": "Report file not found"}

        content = file_path.read_text(encoding="utf-8")
        sections = self.parse_markdown(content)

        # Build week header
        if start_date and end_date:
            week_title = f"第{week_num}周 {start_date.month}.{start_date.day}-{end_date.month}.{end_date.day}"
        else:
            week_title = f"第{week_num}周"

        # Find week section
        week_pattern = rf"^第{week_num}周(?:\s+\d+\.\d+-\d+\.\d+)?$"
        week_idx = None
        week_end_idx = None
        for i, section in enumerate(sections):
            if section.level == 1 and re.match(week_pattern, section.title):
                week_idx = i
                # Update title with date range if provided
                if start_date and end_date:
                    sections[i].title = week_title
                for j in range(i + 1, len(sections)):
                    if sections[j].level == 1:
                        week_end_idx = j
                        break
                if week_end_idx is None:
                    week_end_idx = len(sections)
                break

        if week_idx is None:
            return {"success": False, "error": f"Week {week_num} not found"}

        # Find "待整理周报" section within the week
        raw_content_idx = None
        raw_content = ""
        for i in range(week_idx + 1, week_end_idx):
            if sections[i].level == 2 and "待整理周报" in sections[i].title:
                raw_content_idx = i
                raw_content = sections[i].content
                break

        if raw_content_idx is None or not raw_content.strip():
            return {"success": False, "error": "未找到 '待整理周报' 段落或内容为空"}

        # Parse member content from raw_content
        # The raw content contains ## 成员名 sections
        # We need to parse these from the raw text
        member_pattern = r"^##\s+(.+)$"
        lines = raw_content.split("\n")

        members_data = {}  # {member_name: content}
        current_member = None
        current_content = []

        for line in lines:
            member_match = re.match(member_pattern, line)
            if member_match:
                # Save previous member
                if current_member:
                    members_data[current_member] = "\n".join(current_content).strip()
                current_member = member_match.group(1).strip()
                current_content = []
            else:
                if current_member:
                    current_content.append(line)

        # Don't forget the last member
        if current_member:
            members_data[current_member] = "\n".join(current_content).strip()

        if not members_data:
            return {"success": False, "error": "未在待整理周报中找到成员内容（格式：## 成员名）"}

        # Build new week sections
        new_week_sections = [sections[week_idx]]  # Keep week header

        # Add empty "待整理周报" section (cleared)
        new_week_sections.append(MarkdownSection(level=2, title="待整理周报", content=""))

        # Check if team summary exists and preserve it
        for i in range(week_idx + 1, week_end_idx):
            if sections[i].level == 2 and "本周团队重点工作总结" in sections[i].title:
                new_week_sections.append(sections[i])
                break
        else:
            new_week_sections.append(MarkdownSection(level=2, title="本周团队重点工作总结", content=""))

        # Collect existing members (to preserve their data if any)
        existing_members = {}
        for i in range(week_idx + 1, week_end_idx):
            if sections[i].level == 2 and "待整理周报" not in sections[i].title and "本周团队重点工作总结" not in sections[i].title:
                member_name = sections[i].title
                # Collect all content for this member
                member_sections = [sections[i]]
                for j in range(i + 1, week_end_idx):
                    if sections[j].level <= 2:
                        break
                    member_sections.append(sections[j])
                existing_members[member_name] = member_sections

        # Process each member from raw content
        members_found = []
        for member_name, raw_member_content in members_data.items():
            members_found.append(member_name)

            # Clean up content: remove "**今日工作总结**" header
            clean_content = re.sub(r"\*\*今日工作总结\*\*\s*\n*", "", raw_member_content)
            clean_content = clean_content.strip()

            # Create proper structure
            member_section = MarkdownSection(level=2, title=member_name, content="")
            new_week_sections.append(member_section)

            # Add ### 本周工作总结
            summary_section = MarkdownSection(level=3, title="本周工作总结", content="")
            new_week_sections.append(summary_section)

            # Add #### 🤖 Agent 总结
            agent_section = MarkdownSection(level=4, title="🤖 Agent 总结", content="*[待 Agent 生成总结]*")
            new_week_sections.append(agent_section)

            # Add #### 个人总结 with the content
            personal_section = MarkdownSection(level=4, title="个人总结", content=clean_content)
            new_week_sections.append(personal_section)

            # Add #### 工作明细
            details_section = MarkdownSection(level=4, title="工作明细", content="*[待生成工作明细]*")
            new_week_sections.append(details_section)

        # Add any existing members not in the new data (preserve them)
        for member_name, member_sections in existing_members.items():
            if member_name not in members_data:
                new_week_sections.extend(member_sections)

        # Rebuild sections: keep everything before week, add new week content, keep everything after
        final_sections = sections[:week_idx] + new_week_sections + sections[week_end_idx:]

        # Write back
        new_content = self.sections_to_markdown(final_sections)
        file_path.write_text(new_content, encoding="utf-8")

        return {
            "success": True,
            "members_organized": members_found,
            "message": f"已整理 {len(members_found)} 位成员的周报: {', '.join(members_found)}"
        }

    def list_reports(self) -> list[tuple[int, int]]:
        """
        List all available reports.

        Returns:
            List of (year, month) tuples
        """
        reports = []
        for file_path in self.reports_dir.glob("*.md"):
            match = re.match(r"(\d{4})-(\d{2})\.md", file_path.name)
            if match:
                year, month = int(match.group(1)), int(match.group(2))
                reports.append((year, month))
        return sorted(reports)