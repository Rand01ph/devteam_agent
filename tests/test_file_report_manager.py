"""Tests for file-based weekly report organization."""

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.report.file_report_manager import FileReportManager


class FileReportManagerTests(unittest.TestCase):
    """Focused tests for organizing weekly reports from _pending.md."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.reports_dir = Path(self.temp_dir.name)
        self.manager = FileReportManager(
            str(self.reports_dir),
            ["acct_alpha", "acct_beta", "acct_gamma", "acct_delta", "acct_lead"],
            {
                "alias-alpha": "acct_alpha",
                "alias-beta": "acct_beta",
                "alias-delta": "acct_delta",
            },
        )
        self.week_dir = self.reports_dir / "2026-03" / "0316-0322"
        self.week_dir.mkdir(parents=True)
        (self.week_dir / "_meta.json").write_text(
            json.dumps(
                {
                    "year": 2026,
                    "month": 3,
                    "week_num": 12,
                    "start_date": date(2026, 3, 16).isoformat(),
                    "end_date": date(2026, 3, 22).isoformat(),
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_organize_week_content_uses_account_names_and_skips_unknown_members(self) -> None:
        """Known account-name sections are organized and unknown sections are skipped."""
        pending_content = """## acct_alpha

**本周工作总结**

1. finish parser spike
2. add queue retry logging

**AI相关事项总结**

reviewed a mock automation flow

## acct_beta

**本周工作总结**

## **ops-lane**

- trim stale cache records

## **metrics**

- validate synthetic scorecard formula

**AI相关事项总结**

experimented with local skill chaining

## outsider_name

**本周工作总结**

this block should be skipped

## acct_delta

**本周工作总结**

**batch-edit：**

1. support bulk edit for labels

**AI相关：**

1. compare two prompt layouts
"""
        (self.week_dir / "_pending.md").write_text(pending_content, encoding="utf-8")

        result = self.manager.organize_week_content(2026, 3, 12)

        self.assertTrue(result["success"])
        self.assertEqual(result["members_written"], ["acct_alpha", "acct_beta", "acct_delta"])
        self.assertEqual(result["unknown_members_skipped"], ["outsider_name"])
        self.assertEqual((self.week_dir / "_pending.md").read_text(encoding="utf-8"), "")

        alpha_report = (self.week_dir / "acct_alpha.md").read_text(encoding="utf-8")
        self.assertIn("#### 个人总结", alpha_report)
        self.assertIn("1. finish parser spike", alpha_report)
        self.assertIn("AI相关事项总结：", alpha_report)
        self.assertIn("reviewed a mock automation flow", alpha_report)

        beta_report = (self.week_dir / "acct_beta.md").read_text(encoding="utf-8")
        self.assertIn("## **ops-lane**", beta_report)
        self.assertIn("## **metrics**", beta_report)
        self.assertIn("experimented with local skill chaining", beta_report)

        delta_report = (self.week_dir / "acct_delta.md").read_text(encoding="utf-8")
        self.assertIn("support bulk edit for labels", delta_report)
        self.assertIn("compare two prompt layouts", delta_report)

    def test_organize_week_content_preserves_existing_sections(self) -> None:
        """Existing agent summary and work details are preserved when replacing personal summary."""
        existing_report = """### 本周工作总结

#### 🤖 Agent 总结

已有 Agent 总结

#### 个人总结

旧的个人总结

#### 工作明细

已有工作明细
"""
        (self.week_dir / "acct_lead.md").write_text(existing_report, encoding="utf-8")
        (self.week_dir / "_pending.md").write_text(
            """## acct_lead

release notes

1. coordinate a staged rollout

summary
the lead focused on rollout planning and incident follow-up.
""",
            encoding="utf-8",
        )

        result = self.manager.organize_week_content(2026, 3, 12)

        self.assertTrue(result["success"])
        updated_report = (self.week_dir / "acct_lead.md").read_text(encoding="utf-8")
        self.assertIn("已有 Agent 总结", updated_report)
        self.assertIn("已有工作明细", updated_report)
        self.assertIn("release notes", updated_report)
        self.assertIn("the lead focused on rollout planning and incident follow-up.", updated_report)
        self.assertNotIn("旧的个人总结", updated_report)

    def test_organize_week_content_supports_account_names_without_mapping(self) -> None:
        """Account-name headings work directly even when no display-name mapping is configured."""
        manager = FileReportManager(
            str(self.reports_dir),
            ["acct_alpha", "acct_beta"],
            {},
        )
        pending_content = """## acct_alpha

**本周工作总结**

1. align CLI banner copy

## acct_beta

**本周工作总结**

## **delivery-track**

- check synthetic deployment metrics
"""
        (self.week_dir / "_pending.md").write_text(pending_content, encoding="utf-8")

        result = manager.organize_week_content(2026, 3, 12)

        self.assertTrue(result["success"])
        self.assertEqual(result["members_written"], ["acct_alpha", "acct_beta"])
        alpha_report = (self.week_dir / "acct_alpha.md").read_text(encoding="utf-8")
        self.assertIn("align CLI banner copy", alpha_report)
        beta_report = (self.week_dir / "acct_beta.md").read_text(encoding="utf-8")
        self.assertIn("## **delivery-track**", beta_report)

    def test_week_creation_generates_pending_template(self) -> None:
        """Creating a new week directory auto-generates a pending template for all team members."""
        manager = FileReportManager(
            str(self.reports_dir),
            ["acct_alpha", "acct_beta", "acct_gamma"],
            {},
        )

        manager.add_or_update_member_report(
            2026,
            4,
            1,
            "acct_alpha",
            "### 本周工作总结\n\n#### 🤖 Agent 总结\n\nx\n\n#### 个人总结\n\ny\n\n#### 工作明细\n\nz\n",
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 7),
        )

        pending_file = self.reports_dir / "2026-04" / "0401-0407" / "_pending.md"
        self.assertTrue(pending_file.exists())
        template = pending_file.read_text(encoding="utf-8")
        self.assertIn("## acct_alpha", template)
        self.assertIn("## acct_beta", template)
        self.assertIn("## acct_gamma", template)
        self.assertEqual(template.count("**本周工作总结**"), 3)

    def test_prepare_week_report_directory_returns_created_paths(self) -> None:
        """Preparing a week directory returns the expected helper file paths."""
        manager = FileReportManager(
            str(self.reports_dir),
            ["acct_alpha", "acct_beta"],
            {},
        )

        result = manager.prepare_week_report_directory(
            2026,
            5,
            2,
            start_date=date(2026, 5, 11),
            end_date=date(2026, 5, 17),
        )

        self.assertTrue(result["success"])
        self.assertIn("0511-0517", result["week_dir"])
        self.assertTrue(Path(result["pending_file"]).exists())
        self.assertTrue(Path(result["meta_file"]).exists())
        pending_template = Path(result["pending_file"]).read_text(encoding="utf-8")
        self.assertIn("## acct_alpha", pending_template)
        self.assertIn("## acct_beta", pending_template)

    def test_add_or_update_member_report_merges_sections_instead_of_overwriting(self) -> None:
        """Updating only one section should preserve other existing sections."""
        existing_report = """### 本周工作总结

#### 🤖 Agent 总结

已有 Agent 总结

#### 个人总结

已有个人总结

#### 工作明细

旧工作明细
"""
        (self.week_dir / "acct_alpha.md").write_text(existing_report, encoding="utf-8")

        update_only_details = """### 本周工作总结

#### 工作明细

新工作明细A
新工作明细B
"""
        self.manager.add_or_update_member_report(
            2026,
            3,
            12,
            "acct_alpha",
            update_only_details,
        )

        updated_report = (self.week_dir / "acct_alpha.md").read_text(encoding="utf-8")
        self.assertIn("已有 Agent 总结", updated_report)
        self.assertIn("已有个人总结", updated_report)
        self.assertIn("新工作明细A", updated_report)
        self.assertIn("新工作明细B", updated_report)
        self.assertNotIn("旧工作明细", updated_report)


if __name__ == "__main__":
    unittest.main()
