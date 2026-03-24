"""FastAPI Web application for DevTeam Agent."""

import asyncio
import json
import re
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv

from claude_agent_sdk import (
    AgentDefinition,
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
        claude_env = self.config.claude.to_env_dict()

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
        report_generator = ReportGenerator(
            gitlab_client,
            jira_client,
            claude_env=claude_env,
            claude_model=self.config.claude.model,
            cwd=str(PROJECT_ROOT),
        )

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
2. 先调用 `finalize_weekly_report` 工具，完成周目录准备和成员周报整理
3. 再调用 `read_weekly_report_bundle` 获取本周完整上下文
4. 对每位成员：
   - 如果 `#### 个人总结` 仍是占位符或质量不足，必须使用 `member-personal-summarizer` 子代理生成个人总结
   - 再调用 `update_member_personal_summary` 写回
5. 所有成员个人总结完成后：
   - 必须使用 `team-weekly-summarizer` 子代理生成团队总结
   - 再调用 `update_team_summary` 写回
6. 汇报整理结果（包括已跳过的未知成员和最终团队总结）

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
        options = ClaudeAgentOptions(
            mcp_servers={"devteam": mcp_server},
            allowed_tools=["Read", "Write", "Skill", "Task"] + tool_names,
            permission_mode="acceptEdits",
            system_prompt=system_prompt.format(
                team_members=", ".join(self.config.team_members)
            ),
            env=claude_env if claude_env else {},
            setting_sources=["project"],
            cwd=str(PROJECT_ROOT),
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


def _get_reports_dir(config: AgentConfig) -> Path:
    """Resolve the configured reports directory against the project root."""
    reports_dir = Path(config.reports_dir)
    if not reports_dir.is_absolute():
        reports_dir = PROJECT_ROOT / reports_dir
    return reports_dir


def _build_report_manager(config: AgentConfig) -> FileReportManager:
    """Create a report manager for assembling directory-based reports."""
    return FileReportManager(
        config.reports_dir,
        config.team_members,
        config.team_member_name_map,
    )


def _list_report_entries(reports_dir: Path) -> list[dict[str, str]]:
    """List report entries from both directory-based and legacy file-based storage."""
    entries: list[dict[str, str]] = []

    for month_dir in sorted(reports_dir.iterdir(), reverse=True):
        if not month_dir.is_dir():
            continue
        if not re.fullmatch(r"\d{4}-\d{2}", month_dir.name):
            continue
        entries.append({
            "name": f"{month_dir.name}.md",
            "path": str(month_dir.relative_to(PROJECT_ROOT)),
            "source": "directory",
        })

    for file_path in sorted(reports_dir.glob("*.md"), reverse=True):
        if "-bak" in file_path.name or file_path.name.endswith(".legacy"):
            continue
        virtual_name = file_path.name
        if any(entry["name"] == virtual_name for entry in entries):
            continue
        entries.append({
            "name": virtual_name,
            "path": str(file_path.relative_to(PROJECT_ROOT)),
            "source": "file",
        })

    return entries


def _load_report_content(config: AgentConfig, name: str) -> tuple[str, str]:
    """Load report content from either directory-based or legacy file-based storage."""
    reports_dir = _get_reports_dir(config)

    month_match = re.fullmatch(r"(\d{4})-(\d{2})\.md", name)
    if month_match:
        year = int(month_match.group(1))
        month = int(month_match.group(2))
        month_dir = reports_dir / f"{year}-{month:02d}"
        if month_dir.exists() and month_dir.is_dir():
            report_manager = _build_report_manager(config)
            return name, report_manager.read_report(year, month)

    file_path = reports_dir / name
    if file_path.exists() and file_path.is_file():
        return name, file_path.read_text(encoding="utf-8")

    raise FileNotFoundError("Report not found")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render the main page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/reports")
async def list_reports():
    """List all report files."""
    try:
        config = AgentConfig.from_env()
        reports_dir = _get_reports_dir(config)

        if not reports_dir.exists():
            return {"reports": []}

        return {"reports": _list_report_entries(reports_dir)}
    except Exception as e:
        return {"reports": [], "error": str(e)}


@app.get("/api/reports/{name}")
async def get_report(name: str):
    """Get report content."""
    try:
        config = AgentConfig.from_env()
        report_name, content = _load_report_content(config, name)
        return {"name": report_name, "content": content}
    except FileNotFoundError as e:
        return {"error": str(e)}
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
