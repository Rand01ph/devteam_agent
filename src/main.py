"""DevTeam Agent - Main entry point."""

import asyncio
from pathlib import Path
from dotenv import load_dotenv

from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, AssistantMessage, TextBlock, create_sdk_mcp_server

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

        # Initialize Claude client
        tool_names = [f"mcp__devteam__{tool.name}" for tool in self.tools]
        options = ClaudeAgentOptions(
            mcp_servers={"devteam": self.mcp_server},
            allowed_tools=["Read", "Write"] + tool_names,
            permission_mode="acceptEdits"
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

            # Send message
            await self.client.query(user_input)
            self.turn_count += 1

            # Process response
            print(f"[{self.turn_count}] Agent: ", end="")
            async for message in self.client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            print(block.text, end="")
            print()  # New line after response

        await self.client.disconnect()
        print(f"\n对话结束，共 {self.turn_count} 轮。")


async def main():
    """Main entry point."""
    agent = DevTeamAgent()
    await agent.start()


if __name__ == "__main__":
    asyncio.run(main())