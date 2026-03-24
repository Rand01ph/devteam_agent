"""DevTeam Agent - Main entry point."""

import asyncio
import locale
import sys
from pathlib import Path
from dotenv import load_dotenv

from claude_agent_sdk import (
    AgentDefinition,
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
    ThinkingBlock,
    ResultMessage,
    SystemMessage,
    create_sdk_mcp_server
)

from src.config import AgentConfig
from src.integrations.gitlab_client import GitLabClient
from src.integrations.jira_client import JiraClient
from src.report.file_report_manager import FileReportManager
from src.report.generator import ReportGenerator
from src.tools.report_tools import create_report_tools
from src.tools.gitlab_tools import create_gitlab_tools
from src.tools.jira_tools import create_jira_tools
from src.tools.time_tools import create_time_tools


class DevTeamAgent:
    """DevTeam management agent powered by Claude."""

    def __init__(self):
        """Initialize the DevTeam Agent."""
        # Load environment variables
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path, override=True)

        # Load configuration
        try:
            self.config = AgentConfig.from_env()
        except ValueError as e:
            print(f"配置错误: {e}")
            print("请检查 .env 文件中的配置。")
            raise

        # Build Claude env dict from config
        claude_env = self.config.claude.to_env_dict()

        # Initialize clients
        self.gitlab_client = GitLabClient(
            self.config.gitlab.url,
            self.config.gitlab.token,
            self.config.gitlab.project_ids
        )

        self.jira_client = JiraClient(
            self.config.jira.url,
            self.config.jira.username,
            self.config.jira.api_token,
            self.config.jira.project_keys
        )

        # Initialize report manager
        self.report_manager = FileReportManager(
            self.config.reports_dir,
            self.config.team_members,
            self.config.team_member_name_map,
        )

        # Initialize report generator
        self.report_generator = ReportGenerator(
            self.gitlab_client,
            self.jira_client,
            claude_env=claude_env,
            claude_model=self.config.claude.model,
            cwd=str(Path(__file__).parent.parent),
        )

        # Create MCP tools
        self.tools = []
        self.tools.extend(create_time_tools())  # Time tools first for date/time awareness
        self.tools.extend(create_report_tools(
            self.report_manager,
            self.report_generator,
            self.config
        ))
        self.tools.extend(create_gitlab_tools(self.gitlab_client))
        self.tools.extend(create_jira_tools(self.jira_client))

        # Create MCP server
        self.mcp_server = create_sdk_mcp_server(
            name="devteam",
            version="0.1.0",
            tools=self.tools
        )

        # System prompt for the agent
        system_prompt = """你是 DevTeam Agent，一个专业的团队工作管理助手。你的主要职责是帮助团队生成和管理周报。

## 周报结构

正式周报使用目录化结构存储：
- `data/reports/YYYY-MM/MMDD-MMDD/<account>.md`
- `data/reports/YYYY-MM/MMDD-MMDD/_team_summary.md`
- `data/reports/YYYY-MM/MMDD-MMDD/_pending.md`

其中 `_pending.md` 是每周的待整理输入稿，用户会把原始周报内容粘贴到这里。
推荐直接使用账号名作为成员标题，例如 `## huangjingfang`。

## 周报整理规则

当用户说"整理周报"或类似指令时：
1. 确定日期范围（年、月、周数、起止日期）
2. 优先调用 `finalize_weekly_report` 工具，完成周目录准备和成员周报整理
3. 然后调用 `read_weekly_report_bundle` 获取完整周报上下文
4. 对每位成员：
   - 如果 `#### 个人总结` 仍是占位符或明显质量不足，必须使用 `member-personal-summarizer` 子代理生成个人总结
   - 再调用 `update_member_personal_summary` 写回
5. 所有成员个人总结完成后：
   - 必须使用 `team-weekly-summarizer` 子代理生成团队总结
   - 再调用 `update_team_summary` 写回
6. `finalize_weekly_report` 工具只负责：
   - 准备周目录（如不存在）
   - 从目标周目录的 `_pending.md` 中读取原始内容并整理成员周报
   - 按账号名切分成员内容
   - 提取 `**本周工作总结**`，并将 `**AI相关事项总结**` / `**AI相关：**` 追加到个人总结
   - 写入成员周报和月度 markdown 快照
7. 整理完成后，汇报已整理成员、已跳过的未知成员以及最终团队总结

## 注意事项

- 总结要简洁，不超过 3-4 句话
- 使用中文
- 基于实际数据，不要编造内容
- 可以用**加粗**突出重点工作
- 如果活动较少，如实说明即可
- 整理周报后，汇报已整理的成员列表
- 团队总结默认输出为正式 Markdown 周报风格：
  `## 本周重点工作记录` 下固定包含
  `### 重点开发及维护进展`、`### 组织级配置管理`、`### 产研公共事项支持`、`### 横向沟通及汇报`、`### 运维工作`、`### 团队管理 (AI 转型实践)`
- 其中 `### 重点开发及维护进展` 必须优先按业务主题分组，例如 `- **Portal & 资配**`，并在主题下继续用 `- **【子模块】** 结果描述。` 组织内容
- 不要输出成员工作概览表、本周亮点、待关注等附加模块，除非用户明确要求

## 可用团队成员
{team_members}
"""

        # Initialize Claude client
        tool_names = [f"mcp__devteam__{tool.name}" for tool in self.tools]
        options = ClaudeAgentOptions(
            mcp_servers={"devteam": self.mcp_server},
            allowed_tools=["Read", "Write", "Skill", "Task"] + tool_names,
            permission_mode="acceptEdits",
            system_prompt=system_prompt.format(team_members=", ".join(self.config.team_members)),
            env=claude_env if claude_env else {},
            setting_sources=["project"],
            cwd=str(Path(__file__).parent.parent),
            agents={
                ReportGenerator.MEMBER_SUMMARY_SUBAGENT_NAME: AgentDefinition(
                    description=ReportGenerator.MEMBER_SUMMARY_SUBAGENT_DESCRIPTION,
                    prompt=ReportGenerator.MEMBER_SUMMARY_SYSTEM_PROMPT,
                    tools=[],
                    model="inherit",
                ),
                ReportGenerator.TEAM_SUMMARY_SUBAGENT_NAME: AgentDefinition(
                    description=ReportGenerator.TEAM_SUMMARY_SUBAGENT_DESCRIPTION,
                    prompt=ReportGenerator.TEAM_SUMMARY_SYSTEM_PROMPT,
                    tools=[],
                    model="inherit",
                ),
            },
        )

        self.client = ClaudeSDKClient(options)
        self.turn_count = 0

    def _read_console_input(self, prompt: str) -> str:
        """Read one line from stdin with defensive decoding.

        Some terminal/IME combinations can surface console bytes that fail
        `input()`'s default UTF-8 text decoding. Reading the raw bytes lets us
        decode with a small fallback chain instead of crashing the session.
        """
        print(prompt, end="", flush=True)

        raw_line = sys.stdin.buffer.readline()
        if raw_line == b"":
            raise EOFError

        if raw_line.endswith(b"\n"):
            raw_line = raw_line[:-1]
        if raw_line.endswith(b"\r"):
            raw_line = raw_line[:-1]

        encodings: list[str] = []
        for encoding in (
            sys.stdin.encoding,
            locale.getpreferredencoding(False),
            sys.getfilesystemencoding(),
            "utf-8",
            "utf-8-sig",
            "gb18030",
            "gbk",
            "big5",
        ):
            if encoding and encoding not in encodings:
                encodings.append(encoding)

        for encoding in encodings:
            try:
                return raw_line.decode(encoding)
            except UnicodeDecodeError:
                continue

        # Preserve forward progress even if the terminal emitted unexpected bytes.
        return raw_line.decode("utf-8", errors="replace")

    async def start(self):
        """Start the agent conversation session."""
        await self.client.connect()

        print("=" * 60)
        print("DevTeam Agent - 团队工作管理助手")
        print("=" * 60)
        print(f"团队成员: {', '.join(self.config.team_members)}")
        print(f"周报目录: {self.config.reports_dir}")
        print("\n可用命令:")
        print("  - 'exit': 退出")
        print("  - 'interrupt': 中断当前任务")
        print("  - 'new': 开始新对话")
        print("\n示例问题:")
        print("  - 准备第12周周报目录，时间是 2026-03-16 到 2026-03-22")
        print("  - 生成 huangjingfang 本周的周报")
        print("  - 查看本月所有周报")
        print("  - 用固定流水线整理第12周周报，时间是 2026-03-16 到 2026-03-22")
        print("  - 重新生成第12周的团队总结")
        print("  - 查看 chenjunli 在GitLab上的活动")
        print("=" * 60)

        while True:
            user_input = self._read_console_input(f"\n[{self.turn_count + 1}] 你: ")

            if user_input.lower() == 'exit':
                break
            elif user_input.lower() == 'interrupt':
                await self.client.interrupt()
                print("任务已中断!")
                continue
            elif user_input.lower() == 'new':
                await self.client.disconnect()
                await self.client.connect()
                self.turn_count = 0
                print("已开始新对话（之前的上下文已清除）")
                continue

            # Send message and show processing indicator
            print("\n⏳ 正在处理...", flush=True)
            await self.client.query(user_input)
            self.turn_count += 1

            # Process response with progress feedback
            response_started = False
            async for message in self.client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, ToolUseBlock):
                            # Show tool being called
                            tool_display_name = block.name.replace("mcp__devteam__", "")
                            print(f"🔧 调用工具: {tool_display_name}", flush=True)
                        elif isinstance(block, ThinkingBlock):
                            # Show thinking indicator
                            print("🤔 思考中...", flush=True)
                        elif isinstance(block, TextBlock):
                            if not response_started:
                                print(f"\n[{self.turn_count}] Agent: ", end="", flush=True)
                                response_started = True
                            print(block.text, end="", flush=True)
                elif isinstance(message, ResultMessage):
                    # Show completion status
                    if message.duration_ms:
                        duration_sec = message.duration_ms / 1000
                        print(f"\n✅ 完成 (耗时: {duration_sec:.1f}s)", flush=True)

            if not response_started:
                print()  # New line if no text response

        await self.client.disconnect()
        print(f"\n对话结束，共 {self.turn_count} 轮。")

    async def query_once(self, prompt: str) -> str:
        """Send a single query and return the full text response.

        Intended for programmatic use (e.g. E2E tests, scripts).
        Manages its own connect/disconnect lifecycle.
        """
        await self.client.connect()
        try:
            await self.client.query(prompt)
            response_text = ""
            async for message in self.client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            response_text += block.text
            return response_text
        finally:
            await self.client.disconnect()


async def main():
    """Main entry point."""
    agent = DevTeamAgent()
    await agent.start()


if __name__ == "__main__":
    asyncio.run(main())
