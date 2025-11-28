"""Markdown weekly report file management."""

import os
import re
from datetime import datetime, date
from pathlib import Path
from typing import Optional


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
            # Create initial file with title
            file_path.write_text(f"# {year}年{month}月团队周报\n\n")
        return file_path

    def read_report(self, year: int, month: int) -> str:
        """Read report content for a specific month."""
        file_path = self.get_report_file_path(year, month)
        if not file_path.exists():
            return ""
        return file_path.read_text(encoding="utf-8")

    def get_week_section(self, content: str, week_num: int) -> Optional[str]:
        """
        Extract a specific week section from report content.

        Args:
            content: Full report markdown content
            week_num: Week number (1-based)

        Returns:
            The week section content, or None if not found
        """
        # Match week section (# Week N or # 第N周)
        pattern = rf"^# (?:Week {week_num}|第{week_num}周)$"
        lines = content.split("\n")

        start_idx = None
        for i, line in enumerate(lines):
            if re.match(pattern, line):
                start_idx = i
                break

        if start_idx is None:
            return None

        # Find the end of this section (next # heading or end of file)
        end_idx = len(lines)
        for i in range(start_idx + 1, len(lines)):
            if lines[i].startswith("# "):
                end_idx = i
                break

        return "\n".join(lines[start_idx:end_idx])

    def get_member_report(self, content: str, week_num: int, member_name: str) -> Optional[str]:
        """
        Extract a specific member's report for a specific week.

        Args:
            content: Full report markdown content
            week_num: Week number
            member_name: Team member name

        Returns:
            The member's report content, or None if not found
        """
        week_section = self.get_week_section(content, week_num)
        if not week_section:
            return None

        # Match member section (## Member Name)
        pattern = rf"^## {re.escape(member_name)}$"
        lines = week_section.split("\n")

        start_idx = None
        for i, line in enumerate(lines):
            if re.match(pattern, line):
                start_idx = i
                break

        if start_idx is None:
            return None

        # Find the end of this section (next ## heading or end of week section)
        end_idx = len(lines)
        for i in range(start_idx + 1, len(lines)):
            if lines[i].startswith("## "):
                end_idx = i
                break

        return "\n".join(lines[start_idx:end_idx])

    def add_or_update_member_report(
        self,
        year: int,
        month: int,
        week_num: int,
        member_name: str,
        report_content: str
    ) -> None:
        """
        Add or update a member's weekly report.

        Args:
            year: Year
            month: Month
            week_num: Week number
            member_name: Team member name
            report_content: Report content (without member name heading)
        """
        file_path = self.ensure_report_file_exists(year, month)
        content = file_path.read_text(encoding="utf-8")

        # Ensure week section exists
        week_header = f"# 第{week_num}周"
        if week_header not in content:
            content += f"\n{week_header}\n\n"

        # Split by week sections
        lines = content.split("\n")
        new_lines = []
        in_target_week = False
        in_target_member = False
        target_week_pattern = rf"^# 第{week_num}周$"
        target_member_pattern = rf"^## {re.escape(member_name)}$"
        member_section_added = False

        i = 0
        while i < len(lines):
            line = lines[i]

            # Check if we're entering the target week
            if re.match(target_week_pattern, line):
                in_target_week = True
                new_lines.append(line)
                i += 1
                continue

            # Check if we're leaving the target week
            if in_target_week and line.startswith("# "):
                in_target_week = False
                # If we haven't added the member section yet, add it before next week
                if not member_section_added:
                    new_lines.append(f"## {member_name}\n")
                    new_lines.append(report_content)
                    new_lines.append("")
                    member_section_added = True

            # In target week, check for target member
            if in_target_week and re.match(target_member_pattern, line):
                in_target_member = True
                new_lines.append(line)
                # Skip old content until next member or end of week
                i += 1
                while i < len(lines):
                    if lines[i].startswith("## ") or lines[i].startswith("# "):
                        break
                    i += 1
                # Add new content
                new_lines.append(report_content)
                new_lines.append("")
                member_section_added = True
                continue

            # In target week, check if we hit another member (means target member doesn't exist yet)
            if in_target_week and not member_section_added and line.startswith("## "):
                # Insert target member before this member
                new_lines.append(f"## {member_name}\n")
                new_lines.append(report_content)
                new_lines.append("")
                member_section_added = True

            new_lines.append(line)
            i += 1

        # If we're still in target week at the end, add member section
        if in_target_week and not member_section_added:
            new_lines.append(f"## {member_name}\n")
            new_lines.append(report_content)
            new_lines.append("")

        file_path.write_text("\n".join(new_lines), encoding="utf-8")

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