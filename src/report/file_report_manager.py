"""File-based report management replacing the old single-file Markdown approach."""

import json
from datetime import date
from pathlib import Path
from typing import Optional


class FileReportManager:
    """Manages reports using a directory-per-week structure."""

    def __init__(self, reports_dir: str):
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def _get_month_dir(self, year: int, month: int) -> Path:
        return self.reports_dir / f"{year}-{month:02d}"
        
    def _format_date(self, d: date) -> str:
        return f"{d.month:02d}{d.day:02d}"
        
    def _get_week_dir_name(self, start_date: date, end_date: date) -> str:
        return f"{self._format_date(start_date)}-{self._format_date(end_date)}"

    def _find_week_dir_by_num(self, month_dir: Path, week_num: int) -> Optional[Path]:
        """Find a week directory by its week_num stored in _meta.json."""
        if not month_dir.exists():
            return None
            
        for week_dir in month_dir.iterdir():
            if not week_dir.is_dir():
                continue
            meta_file = week_dir / "_meta.json"
            if meta_file.exists():
                try:
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                    if meta.get("week_num") == week_num:
                        return week_dir
                except (json.JSONDecodeError, KeyError):
                    continue
        return None

    def read_report(self, year: int, month: int) -> str:
        """Read and assemble the full monthly report from directories."""
        month_dir = self._get_month_dir(year, month)
        if not month_dir.exists():
            return ""

        lines = [
            f"# {year}年{month}月团队周报\n",
            "# 本月工作总结\n\n"
        ]

        # Get all week directories sorted by name (which is MMDD-MMDD)
        week_dirs = sorted([d for d in month_dir.iterdir() if d.is_dir()])
        
        for week_dir in week_dirs:
            meta_file = week_dir / "_meta.json"
            if not meta_file.exists():
                continue
                
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            week_num = meta.get("week_num")
            start_str = meta.get("start_date")
            end_str = meta.get("end_date")
            
            # Format week header
            if start_str and end_str:
                start_d = date.fromisoformat(start_str)
                end_d = date.fromisoformat(end_str)
                lines.append(f"# 第{week_num}周 {start_d.month}.{start_d.day}-{end_d.month}.{end_d.day}\n")
            else:
                lines.append(f"# 第{week_num}周\n")

            # 1. Add pending report section (if exists)
            pending_file = week_dir / "_pending.md"
            if pending_file.exists():
                content = pending_file.read_text(encoding="utf-8").strip()
                if content:
                    lines.append(f"## 待整理周报\n\n{content}\n")

            # 2. Add team summary section (if exists)
            summary_file = week_dir / "_team_summary.md"
            if summary_file.exists():
                content = summary_file.read_text(encoding="utf-8").strip()
                if content:
                    lines.append(f"## 本周团队重点工作总结\n\n{content}\n")

            # 3. Add all member reports
            for member_file in sorted(week_dir.glob("*.md")):
                if member_file.name.startswith("_"):
                    continue
                    
                member_name = member_file.stem
                content = member_file.read_text(encoding="utf-8").strip()
                if content:
                    lines.append(f"## {member_name}\n\n{content}\n")

        return "\n".join(lines)

    def get_member_report(self, content: str, week_num: int, member_name: str) -> Optional[str]:
        """Extract a specific member's report for a specific week.
        Note: The 'content' parameter is kept for backward compatibility with 
        the old report_tools.py interface, but we actually read directly from the file.
        """
        for month_dir in self.reports_dir.iterdir():
            if not month_dir.is_dir():
                continue
                
            week_dir = self._find_week_dir_by_num(month_dir, week_num)
            if week_dir:
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
        end_date: Optional[date] = None
    ) -> None:
        """Add or update a member's weekly report."""
        month_dir = self._get_month_dir(year, month)
        month_dir.mkdir(parents=True, exist_ok=True)
        
        # Try to find existing week dir
        week_dir = self._find_week_dir_by_num(month_dir, week_num)
        
        if not week_dir and start_date and end_date:
            # Create new week dir
            dir_name = self._get_week_dir_name(start_date, end_date)
            week_dir = month_dir / dir_name
            week_dir.mkdir(parents=True, exist_ok=True)
            
            # Save meta
            meta = {
                "year": year,
                "month": month,
                "week_num": week_num,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            }
            (week_dir / "_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
            
        if not week_dir:
            raise ValueError(f"Week {week_num} directory not found and no dates provided to create it.")
            
        # Write member report
        member_file = week_dir / f"{member_name}.md"
        # Ensure we don't have the ## member_name heading in the file itself
        content = report_content.strip()
        prefix = f"## {member_name}"
        if content.startswith(prefix):
            content = content[len(prefix):].strip()
            
        member_file.write_text(content, encoding="utf-8")

    def organize_week_content(
        self,
        year: int,
        month: int,
        week_num: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> dict:
        """Organize the raw content in _pending.md into proper member structures."""
        month_dir = self._get_month_dir(year, month)
        week_dir = self._find_week_dir_by_num(month_dir, week_num)
        
        if not week_dir:
            return {"success": False, "error": f"Week {week_num} directory not found"}
            
        pending_file = week_dir / "_pending.md"
        if not pending_file.exists():
            return {"success": False, "error": "未找到待整理内容 (_pending.md)"}
            
        content = pending_file.read_text(encoding="utf-8")
        if not content.strip():
            return {"success": False, "error": "待整理内容为空"}
            
        # Parse member content (assumes ## 成员名 format)
        import re
        members_data = {}
        
        # Check if content is wrapped in a markdown code block
        code_block_match = re.search(r"```(?:markdown)?\s*\n(.*?)```", content, re.DOTALL)
        if code_block_match:
            content = code_block_match.group(1)

        member_pattern = r"^##\s+([^#\n]+)$"
        lines = content.split("\n")
        current_member = None
        current_content: list[str] = []

        for line in lines:
            member_match = re.match(member_pattern, line)
            # Exclude numbered sections like "## 1. xxx" or "## 待整理周报"
            if member_match and not re.match(r"^\d+\.\s*", line) and "待整理周报" not in line and "本周团队重点工作总结" not in line:
                if current_member:
                    members_data[current_member] = "\n".join(current_content).strip()
                current_member = member_match.group(1).strip()
                current_content = []
            else:
                if current_member:
                    current_content.append(line)

        if current_member:
            members_data[current_member] = "\n".join(current_content).strip()
            
        if not members_data:
             return {"success": False, "error": "未找到任何成员内容格式(## 成员名)"}

        members_found = []
        for member_name, raw_content in members_data.items():
            members_found.append(member_name)
            
            # Clean up content
            clean_content = re.sub(r"\*\*今日工作总结\*\*\s*\n*", "", raw_content).strip()
            
            # Format proper structure
            structured_content = (
                "### 本周工作总结\n\n"
                "#### 🤖 Agent 总结\n\n*[待 Agent 生成总结]*\n\n"
                f"#### 个人总结\n\n{clean_content}\n\n"
                "#### 工作明细\n\n*[待生成工作明细]*"
            )
            
            # Save member file
            member_file = week_dir / f"{member_name}.md"
            member_file.write_text(structured_content, encoding="utf-8")
            
        # Clear pending file
        pending_file.write_text("", encoding="utf-8")
        
        # Ensure team summary placeholder exists
        team_summary_file = week_dir / "_team_summary.md"
        if not team_summary_file.exists() or not team_summary_file.read_text().strip():
            team_summary_file.write_text("*[待 Agent 根据各成员周报生成团队总结]*", encoding="utf-8")
            
        return {
            "success": True,
            "members_organized": members_found,
            "message": f"已整理 {len(members_found)} 位成员的周报: {', '.join(members_found)}"
        }

    def list_reports(self) -> list[tuple[int, int]]:
        """List all available reports."""
        reports = []
        for d in self.reports_dir.iterdir():
            if d.is_dir():
                import re
                match = re.match(r"(\d{4})-(\d{2})", d.name)
                if match:
                    year, month = int(match.group(1)), int(match.group(2))
                    reports.append((year, month))
        return sorted(reports)

    def update_team_summary(
        self,
        year: int,
        month: int,
        week_num: int,
        summary_content: str
    ) -> dict:
        """Update the team summary for a specific week."""
        month_dir = self._get_month_dir(year, month)
        week_dir = self._find_week_dir_by_num(month_dir, week_num)
        
        if not week_dir:
             return {"success": False, "error": f"Week {week_num} directory not found"}
             
        summary_file = week_dir / "_team_summary.md"
        
        # Remove header if included in the content
        content = summary_content.strip()
        prefix = "## 本周团队重点工作总结"
        if content.startswith(prefix):
            content = content[len(prefix):].strip()
            
        summary_file.write_text(content, encoding="utf-8")
        
        return {"success": True, "message": f"已更新第{week_num}周的团队工作总结"}
