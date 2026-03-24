"""FastAPI Web application for DevTeam Agent."""

import asyncio
import json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    TextBlock,
    ToolUseBlock,
    ThinkingBlock,
    ResultMessage,
    create_sdk_mcp_server,
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


# Paths
BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Load environment variables
env_path = PROJECT_ROOT / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)

# FastAPI app
app = FastAPI(title="DevTeam Agent")

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Templates
templates = Jinja2Templates(directory=TEMPLATES_DIR)


class AgentSession:
    """Manages a single agent session."""

    def __init__(self):
        self.client: Optional[ClaudeSDKClient] = None
        self.config: Optional[AgentConfig] = None
        self.connected = False

    async def initialize(self):
        """Initialize the agent session."""
        if self.connected:
            return

        # Load configuration
        self.config = AgentConfig.from_env()

        # Initialize clients
        gitlab_client = GitLabClient(
            self.config.gitlab.url,
            self.config.gitlab.token,
            self.config.gitlab.project_ids,
        )

        jira_client = JiraClient(
            self.config.jira.url,
            self.config.jira.username,
            self.config.jira.api_token,
            self.config.jira.project_keys,
        )

        # Initialize report manager
        report_manager = FileReportManager(
            self.config.reports_dir,
            self.config.team_members,
            self.config.team_member_name_map,
        )

        # Initialize report generator
        report_generator = ReportGenerator(gitlab_client, jira_client)

        # Create MCP tools
        tools = []
        tools.extend(create_time_tools())
        tools.extend(create_report_tools(report_manager, report_generator, self.config))
        tools.extend(create_gitlab_tools(gitlab_client))
        tools.extend(create_jira_tools(jira_client))

        # Create MCP server
        mcp_server = create_sdk_mcp_server(
            name="devteam", version="0.1.0", tools=tools
        )

        # System prompt
        system_prompt = """你是 DevTeam Agent，一个专业的团队工作管理助手。你的主要职责是帮助团队生成和管理周报。

## 周报结构

正式周报使用目录化结构存储：
- `data/reports/YYYY-MM/MMDD-MMDD/<account>.md`
- `data/reports/YYYY-MM/MMDD-MMDD/_team_summary.md`
- `data/reports/YYYY-MM/MMDD-MMDD/_pending.md`

其中 `_pending.md` 是每周的待整理输入稿，用户会把原始周报内容粘贴到这里。
推荐直接使用账号名作为成员标题，例如 `## huangjingfang`。

## 周报整理流程（推荐）

当用户说"整理周报"或类似指令时：
1. 确定日期范围（年、月、周数、起止日期）
2. 如果目标周目录还没准备好，先调用 `prepare_week_report_directory` 工具
3. 调用 `organize_weekly_report` 工具
4. 工具会自动：
   - 从目标周目录的 `_pending.md` 中读取原始内容
   - 按账号名识别成员块
   - 提取 `**本周工作总结**`，并把 `**AI相关事项总结**` / `**AI相关：**` 追加到个人总结
   - 更新对应账号名的成员周报文件
   - 清空 `_pending.md`
5. 汇报整理结果（包括已跳过的未知成员）

## 周报生成规则

当你使用 `generate_weekly_report` 工具生成周报后，你必须：

1. **仔细分析**获取到的所有工作明细（GitLab 提交、MR、Jira 工时等）
2. **撰写一段有意义的总结**，替换掉"#### 🤖 Agent 总结"下的占位符
3. 使用 `update_weekly_report` 工具将带有总结的完整内容更新到周报中
4. 总结应该包含：
   - 本周主要完成的工作（用简洁的语言概括）
   - 工作重点和亮点
   - 如果有的话，提及跨项目或跨团队的协作

## 个人总结示例

好的 Agent 总结示例：
> 本周主要工作集中在**技术方案预研**方面，包括利用打卡数据辅助工时填写方案（8h）、研发环境镜像仓库拉取监测方案（8h），预研工作占比超过70%。同时处理了 Portal 系统相关的问题修复。本周 Jira 工时共 40 小时，完成了 idun 复制流水线 bug 修复任务。

## 团队总结生成规则

当所有成员的周报生成完成后，你需要为 `## 本周团队重点工作总结` 生成内容：

1. **综合分析**所有成员的工作内容
2. 生成团队层面的总结，替换掉占位符 `*[待 Agent 根据各成员周报生成团队总结]*`
3. 团队总结应该包含：
   - 本周团队整体工作重点（3-5 项）
   - 主要完成的功能/项目进展
   - 团队协作亮点
   - 下周关注事项（如有）

团队总结示例：
> **本周团队重点工作：**
> 1. **效能度量功能开发**：完成自动化测试覆盖率看板开发，效能度量修复&优化版本上线
> 2. **外发管理功能优化**：外发单失败流程复制问题修复，外发目标显示问题处理
> 3. **配置管理工作推进**：完成多个产品的门禁核查工作，配置管理需求API开发完成
> 4. **团队管理**：完成实习生面试4人

## 注意事项

- 总结要简洁，不超过 3-4 句话
- 使用中文
- 基于实际数据，不要编造内容
- 可以用**加粗**突出重点工作
- 如果活动较少，如实说明即可
- 整理周报后，汇报已整理的成员列表

## 可用团队成员
{team_members}
"""

        # Initialize Claude client
        tool_names = [f"mcp__devteam__{tool.name}" for tool in tools]
        claude_env = self.config.claude.to_env_dict()
        options = ClaudeAgentOptions(
            mcp_servers={"devteam": mcp_server},
            allowed_tools=["Read", "Write", "Skill"] + tool_names,
            permission_mode="acceptEdits",
            system_prompt=system_prompt.format(
                team_members=", ".join(self.config.team_members)
            ),
            env=claude_env if claude_env else {},
            setting_sources=["project"],
            cwd=str(PROJECT_ROOT),
        )

        self.client = ClaudeSDKClient(options)
        await self.client.connect()
        self.connected = True

    async def disconnect(self):
        """Disconnect the agent session."""
        if self.client and self.connected:
            await self.client.disconnect()
            self.connected = False

    async def new_session(self):
        """Start a new conversation session."""
        if self.client and self.connected:
            await self.client.disconnect()
            await self.client.connect()


# Global agent session (single user mode)
agent_session = AgentSession()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render the main page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/reports")
async def list_reports():
    """List all report files."""
    try:
        config = AgentConfig.from_env()
        # Convert relative path to absolute path based on project root
        reports_dir = Path(config.reports_dir)
        if not reports_dir.is_absolute():
            reports_dir = PROJECT_ROOT / reports_dir

        if not reports_dir.exists():
            return {"reports": []}

        files = []
        for f in sorted(reports_dir.glob("*.md"), reverse=True):
            # Skip backup files
            if "-bak" in f.name:
                continue
            files.append({
                "name": f.name,
                "path": str(f.relative_to(PROJECT_ROOT)),
            })

        return {"reports": files}
    except Exception as e:
        return {"reports": [], "error": str(e)}


@app.get("/api/reports/{name}")
async def get_report(name: str):
    """Get report content."""
    try:
        config = AgentConfig.from_env()
        # Convert relative path to absolute path based on project root
        reports_dir = Path(config.reports_dir)
        if not reports_dir.is_absolute():
            reports_dir = PROJECT_ROOT / reports_dir
        file_path = reports_dir / name

        if not file_path.exists():
            return {"error": "Report not found"}

        content = file_path.read_text(encoding="utf-8")
        return {"name": name, "content": content}
    except Exception as e:
        return {"error": str(e)}


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for chat."""
    await websocket.accept()

    try:
        # Initialize agent session
        await agent_session.initialize()

        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message = json.loads(data)

            msg_type = message.get("type")

            if msg_type == "message":
                content = message.get("content", "").strip()
                if not content:
                    continue

                # Send query to agent
                await agent_session.client.query(content)

                # Stream response
                async for response in agent_session.client.receive_response():
                    if isinstance(response, AssistantMessage):
                        for block in response.content:
                            if isinstance(block, ToolUseBlock):
                                tool_name = block.name.replace("mcp__devteam__", "")
                                await websocket.send_json({
                                    "type": "tool_call",
                                    "name": tool_name,
                                })
                            elif isinstance(block, ThinkingBlock):
                                await websocket.send_json({"type": "thinking"})
                            elif isinstance(block, TextBlock):
                                await websocket.send_json({
                                    "type": "text",
                                    "content": block.text,
                                })
                    elif isinstance(response, ResultMessage):
                        await websocket.send_json({
                            "type": "done",
                            "duration_ms": response.duration_ms,
                        })

            elif msg_type == "interrupt":
                if agent_session.client:
                    await agent_session.client.interrupt()
                    await websocket.send_json({
                        "type": "interrupted",
                    })

            elif msg_type == "new_session":
                await agent_session.new_session()
                await websocket.send_json({
                    "type": "session_reset",
                })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e),
            })
        except:
            pass
