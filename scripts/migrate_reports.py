"""Migration script to convert monolithic markdown reports to directory structure."""

import os
import re
import json
from datetime import datetime, date
from pathlib import Path
import sys

# Add project root to path so we can import src modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.report.markdown_manager import MarkdownReportManager, MarkdownSection

def ensure_structured_content(content: str) -> str:
    """Ensure the content has the standard structure even if it's missing pieces."""
    # This matches the basic structure expected by the app
    if "### 本周工作总结" in content:
        return content  # Already structured
        
    structured = "### 本周工作总结\n\n"
    
    if "#### 🤖 Agent 总结" not in content:
        structured += "#### 🤖 Agent 总结\n\n*[待 Agent 生成总结]*\n\n"
        
    structured += f"#### 个人总结\n\n{content}\n\n"
    
    if "#### 工作明细" not in content:
        structured += "#### 工作明细\n\n*[待生成工作明细]*\n"
        
    return structured

def migrate_reports(reports_dir: Path):
    """Migrate all .md files in reports_dir to directory structure."""
    if not reports_dir.exists():
        print(f"Directory {reports_dir} does not exist.")
        return
        
    legacy_manager = MarkdownReportManager(str(reports_dir))
    
    for file_path in reports_dir.glob("*.md"):
        # Skip files that don't look like YYYY-MM.md
        match = re.match(r"(\d{4})-(\d{2})\.md", file_path.name)
        if not match:
            continue
            
        year, month = int(match.group(1)), int(match.group(2))
        month_dir = reports_dir / f"{year}-{month:02d}"
        month_dir.mkdir(exist_ok=True)
        
        print(f"Migrating {file_path.name} to {month_dir.name}/ ...")
        
        content = file_path.read_text(encoding="utf-8")
        sections = legacy_manager.parse_markdown(content)
        
        for i, section in enumerate(sections):
            if section.level == 1 and section.title.startswith("第"):
                # Parse week header: 第11周 03.10-03.16
                week_match = re.match(r"第(\d+)周\s+(\d+)\.(\d+)-(\d+)\.(\d+)", section.title)
                if not week_match:
                    # Try simple format: 第11周
                    week_match = re.match(r"第(\d+)周", section.title)
                    if not week_match:
                        print(f"  Warning: Could not parse week header: {section.title}")
                        continue
                        
                    week_num = int(week_match.group(1))
                    # Fallback dates if none provided
                    start_date = date(year, month, 1)
                    end_date = date(year, month, 7)
                else:
                    week_num = int(week_match.group(1))
                    start_m, start_d = int(week_match.group(2)), int(week_match.group(3))
                    end_m, end_d = int(week_match.group(4)), int(week_match.group(5))
                    
                    # Handle year wrapping around if needed
                    start_y, end_y = year, year
                    if start_m == 12 and end_m == 1:
                        if month == 12: end_y = year + 1
                        else: start_y = year - 1
                        
                    start_date = date(start_y, start_m, start_d)
                    end_date = date(end_y, end_m, end_d)
                
                # Create week dir: 0310-0316
                dir_name = f"{start_date.month:02d}{start_date.day:02d}-{end_date.month:02d}{end_date.day:02d}"
                week_dir = month_dir / dir_name
                week_dir.mkdir(exist_ok=True)
                
                # Write meta.json
                meta = {
                    "year": year,
                    "month": month,
                    "week_num": week_num,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                }
                (week_dir / "_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
                
                # Process subsections for this week
                for j in range(i + 1, len(sections)):
                    if sections[j].level == 1:
                        break  # Next week
                        
                    if sections[j].level == 2:
                        title = sections[j].title.strip()
                        content = sections[j].content.strip()
                        
                        # Collect level 3+ subsections content
                        sub_content = []
                        if content:
                            sub_content.append(content)
                            
                        # Look ahead for sub-sections belonging to this level 2 section
                        for k in range(j + 1, len(sections)):
                            if sections[k].level <= 2:
                                break
                            heading_str = "#" * sections[k].level + " " + sections[k].title
                            sub_content.append(heading_str)
                            if sections[k].content.strip():
                                sub_content.append(sections[k].content.strip())
                                
                        full_content = "\n\n".join(sub_content).strip()
                        
                        if title == "待整理周报":
                            if full_content:
                                (week_dir / "_pending.md").write_text(full_content, encoding="utf-8")
                        elif title == "本周团队重点工作总结":
                            if full_content:
                                (week_dir / "_team_summary.md").write_text(full_content, encoding="utf-8")
                        else:
                            # It's a member report
                            member_name = title
                            
                            # Standardize format if it's raw
                            if "### 本周工作总结" not in full_content and "🤖 Agent 总结" not in full_content:
                                full_content = ensure_structured_content(full_content)
                                
                            if full_content:
                                (week_dir / f"{member_name}.md").write_text(full_content, encoding="utf-8")
                                
                print(f"  ✓ Migrated week {week_num} -> {dir_name}/")
                
        # Rename the legacy file to .legacy so we don't pick it up anymore 
        # but keep it just in case
        legacy_path = file_path.with_suffix(".md.legacy")
        file_path.rename(legacy_path)
        print(f"  ✓ Renamed {file_path.name} -> {legacy_path.name}")
        
    print("\nMigration complete! 🎉")

if __name__ == "__main__":
    reports_dir = Path(__file__).parent.parent / "data" / "reports"
    print(f"Starting migration in: {reports_dir.absolute()}")
    migrate_reports(reports_dir)
