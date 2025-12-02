"""DevTeam Agent - Main entry point."""

import asyncio
from pathlib import Path
from dotenv import load_dotenv

from claude_agent_sdk import (
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
from src.report.markdown_manager import MarkdownReportManager
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
            load_dotenv(env_path)

        # Load configuration
        try:
            self.config = AgentConfig.from_env()
        except ValueError as e:
            print(f"配置错误: {e}")
            print("请检查 .env 文件中的配置。")
            raise

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
        self.report_manager = MarkdownReportManager(self.config.reports_dir)

        # Initialize report generator
        self.report_generator = ReportGenerator(self.gitlab_client, self.jira_client)

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

周报采用以下 Markdown 结构：
```
# 年月团队周报
# 本月工作总结
# 第N周 MM.DD-MM.DD
## 本周团队重点工作总结
## 成员名
### 本周工作总结
#### 🤖 Agent 总结
#### 工作明细
```

## 周报生成规则

当你使用 `generate_weekly_report` 工具生成周报后，你必须：

1. **仔细分析**获取到的所有工作明细（GitLab 提交、MR、Jira 工时等）
2. **撰写一段有意义的总结**，替换掉"#### 🤖 Agent 总结"下的占位符
3. 使用 `update_weekly_report` 工具将带有总结的完整内容更新到周报中
4. 总结应该包含：
   - 本周主要完成的工作（用简洁的语言概括）
   - 工作重点和亮点
   - 如果有的话，提及跨项目或跨团队的协作

## 总结示例

好的总结示例：
> 本周主要工作集中在**技术方案预研**方面，包括利用打卡数据辅助工时填写方案（8h）、研发环境镜像仓库拉取监测方案（8h），预研工作占比超过70%。同时处理了 Portal 系统相关的问题修复。本周 Jira 工时共 40 小时，完成了 idun 复制流水线 bug 修复任务。

## 注意事项

- 总结要简洁，不超过 3-4 句话
- 使用中文
- 基于实际数据，不要编造内容
- 可以用**加粗**突出重点工作
- 如果活动较少，如实说明即可

## 可用团队成员
{team_members}
"""

        # Initialize Claude client
        tool_names = [f"mcp__devteam__{tool.name}" for tool in self.tools]
        options = ClaudeAgentOptions(
            mcp_servers={"devteam": self.mcp_server},
            allowed_tools=["Read", "Write"] + tool_names,
            permission_mode="acceptEdits",
            system_prompt=system_prompt.format(team_members=", ".join(self.config.team_members))
        )

        self.client = ClaudeSDKClient(options)
        self.turn_count = 0

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
        print("  - 生成张三本周的周报")
        print("  - 查看本月所有周报")
        print("  - 总结团队本周的工作")
        print("  - 查看李四在GitLab上的活动")
        print("=" * 60)

        while True:
            user_input = input(f"\n[{self.turn_count + 1}] 你: ")

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


async def main():
    """Main entry point."""
    agent = DevTeamAgent()
    await agent.start()


if __name__ == "__main__":
    asyncio.run(main())