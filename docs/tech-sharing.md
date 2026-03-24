# 基于 Claude Agent SDK 快速开发 AI Agent 实战

> 以 DevTeam Agent（团队周报管理助手）为例

---

## 目录

1. [Claude Agent SDK 简介](#1-claude-agent-sdk-简介)
2. [核心概念与架构](#2-核心概念与架构)
3. [快速开始：5 步构建你的 Agent](#3-快速开始5-步构建你的-agent)
4. [DevTeam Agent 功能拆解](#4-devteam-agent-功能拆解)
5. [项目迭代历程](#5-项目迭代历程)
6. [最佳实践与经验总结](#6-最佳实践与经验总结)

---

## 1. Claude Agent SDK 简介

### 什么是 Claude Agent SDK？

Claude Agent SDK 是 Anthropic 提供的官方 Python SDK，用于构建基于 Claude 的智能代理应用。它提供了：

- **MCP (Model Context Protocol)** 支持：标准化的工具调用协议
- **流式响应**：实时获取 Agent 的思考过程和输出
- **会话管理**：自动维护对话上下文
- **工具集成**：通过 `@tool` 装饰器快速定义工具

### 核心优势

| 特性 | 说明 |
|------|------|
| **简单易用** | 几行代码即可创建一个功能完整的 Agent |
| **标准化** | 基于 MCP 协议，工具定义规范统一 |
| **异步支持** | 原生 async/await，适合 I/O 密集型任务 |
| **流式输出** | 实时反馈，提升用户体验 |

---

## 2. 核心概念与架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      用户交互层                              │
│                  (CLI / Web / API)                          │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                  ClaudeSDKClient                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   connect   │  │    query    │  │  receive_response   │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                    MCP Server                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                   Tools Registry                        │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │ │
│  │  │ Tool 1   │ │ Tool 2   │ │ Tool 3   │ │ Tool N   │   │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 核心组件

#### 1) ClaudeSDKClient - 客户端

```python
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

# 配置选项
options = ClaudeAgentOptions(
    mcp_servers={"my_agent": mcp_server},     # MCP 服务器
    allowed_tools=["Read", "Write"] + tools,   # 允许的工具
    permission_mode="acceptEdits",             # 权限模式
    system_prompt="你是一个智能助手..."         # 系统提示词
)

# 创建客户端
client = ClaudeSDKClient(options)
```

#### 2) MCP Server - 工具服务器

```python
from claude_agent_sdk import create_sdk_mcp_server

mcp_server = create_sdk_mcp_server(
    name="my_agent",      # 服务器名称（工具命名空间）
    version="0.1.0",      # 版本
    tools=tools           # 工具列表
)
```

#### 3) @tool 装饰器 - 工具定义

```python
from claude_agent_sdk import tool

@tool(
    "tool_name",           # 工具名称
    "工具描述...",          # 描述（Claude 会根据描述决定何时调用）
    {                      # 参数模式
        "param1": str,
        "param2": int
    }
)
async def tool_name(args: dict[str, Any]):
    # 实现逻辑
    result = do_something(args["param1"], args["param2"])

    # 返回 MCP 格式响应
    return {
        "content": [{
            "type": "text",
            "text": f"结果: {result}"
        }]
    }
```

### 2.3 消息类型

SDK 定义了多种消息类型用于处理 Agent 响应：

```python
from claude_agent_sdk import (
    AssistantMessage,  # Agent 回复消息
    TextBlock,         # 文本内容块
    ToolUseBlock,      # 工具调用块
    ThinkingBlock,     # 思考过程块
    ResultMessage,     # 完成消息（包含执行时间）
)
```

处理示例：

```python
async for message in client.receive_response():
    if isinstance(message, AssistantMessage):
        for block in message.content:
            if isinstance(block, TextBlock):
                print(block.text)  # 输出文本
            elif isinstance(block, ToolUseBlock):
                print(f"调用工具: {block.name}")
            elif isinstance(block, ThinkingBlock):
                print("思考中...")
    elif isinstance(message, ResultMessage):
        print(f"完成，耗时: {message.duration_ms}ms")
```

---

## 3. 快速开始：5 步构建你的 Agent

### Step 1: 安装依赖

```bash
# 使用 uv (推荐)
uv add claude-agent-sdk

# 或使用 pip
pip install claude-agent-sdk
```

### Step 2: 定义工具

创建 `tools.py`：

```python
from typing import Any
from claude_agent_sdk import tool

def create_my_tools():
    """创建工具的工厂函数"""

    @tool(
        "greet",
        "向用户打招呼",
        {"name": str}
    )
    async def greet(args: dict[str, Any]):
        name = args["name"]
        return {
            "content": [{
                "type": "text",
                "text": f"你好，{name}！很高兴认识你！"
            }]
        }

    @tool(
        "calculate",
        "执行数学计算",
        {"expression": str}
    )
    async def calculate(args: dict[str, Any]):
        try:
            result = eval(args["expression"])  # 仅示例，生产环境需安全处理
            return {
                "content": [{
                    "type": "text",
                    "text": f"计算结果: {result}"
                }]
            }
        except Exception as e:
            return {
                "content": [{
                    "type": "text",
                    "text": f"计算错误: {e}"
                }]
            }

    return [greet, calculate]
```

### Step 3: 创建 Agent 主程序

创建 `main.py`：

```python
import asyncio
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    TextBlock,
    ToolUseBlock,
    ResultMessage,
    create_sdk_mcp_server,
)
from tools import create_my_tools


class MyAgent:
    def __init__(self):
        # 1. 创建工具
        self.tools = create_my_tools()

        # 2. 创建 MCP 服务器
        self.mcp_server = create_sdk_mcp_server(
            name="my_agent",
            version="0.1.0",
            tools=self.tools
        )

        # 3. 构建工具名称列表
        tool_names = [f"mcp__my_agent__{t.name}" for t in self.tools]

        # 4. 配置 Agent
        options = ClaudeAgentOptions(
            mcp_servers={"my_agent": self.mcp_server},
            allowed_tools=tool_names,
            permission_mode="acceptEdits",
            system_prompt="你是一个友好的助手，可以打招呼和做计算。"
        )

        # 5. 创建客户端
        self.client = ClaudeSDKClient(options)

    async def chat(self, message: str):
        """发送消息并获取响应"""
        await self.client.query(message)

        response_text = ""
        async for msg in self.client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        response_text += block.text
                    elif isinstance(block, ToolUseBlock):
                        print(f"[调用工具: {block.name}]")
            elif isinstance(msg, ResultMessage):
                print(f"[完成: {msg.duration_ms}ms]")

        return response_text

    async def run(self):
        """运行交互式对话"""
        await self.client.connect()

        print("Agent 已启动！输入 'exit' 退出。")
        while True:
            user_input = input("\n你: ")
            if user_input.lower() == 'exit':
                break

            response = await self.chat(user_input)
            print(f"\nAgent: {response}")

        await self.client.disconnect()


async def main():
    agent = MyAgent()
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
```

### Step 4: 运行

```bash
python main.py
```

### Step 5: 测试

```
Agent 已启动！输入 'exit' 退出。

你: 你好，我叫 zhangsan
[调用工具: greet]
[完成: 1234ms]

Agent: 你好，zhangsan！很高兴认识你！

你: 计算 (1 + 2) * 3
[调用工具: calculate]
[完成: 987ms]

Agent: 计算结果是 9。
```

---

## 4. DevTeam Agent 功能拆解

### 4.1 项目概述

DevTeam Agent 是一个团队工作管理助手，集成 GitLab 和 Jira，自动生成和管理团队周报。

### 4.2 项目结构

```
devteam_agent/
├── src/
│   ├── main.py                 # CLI 入口
│   ├── config.py               # 配置管理
│   ├── integrations/           # 第三方集成
│   │   ├── gitlab_client.py    # GitLab API 客户端
│   │   └── jira_client.py      # Jira API 客户端
│   ├── tools/                  # MCP 工具
│   │   ├── time_tools.py       # 时间工具 (3个)
│   │   ├── gitlab_tools.py     # GitLab 工具 (3个)
│   │   ├── jira_tools.py       # Jira 工具 (3个)
│   │   └── report_tools.py     # 报告工具 (8个)
│   ├── report/                 # 报告管理
│   │   ├── generator.py        # 报告生成器
│   │   └── markdown_manager.py # Markdown 解析器
│   └── web/                    # Web 界面
│       ├── app.py              # FastAPI 应用
│       ├── templates/          # HTML 模板
│       └── static/             # 静态资源
├── data/reports/               # 周报存储
└── pyproject.toml
```

### 4.3 工具清单 (共 17 个)

#### 时间工具 (3 个)

| 工具名 | 功能 | 使用场景 |
|--------|------|----------|
| `get_current_time` | 获取当前时间信息 | "今天是几号？本周是第几周？" |
| `get_date_range` | 计算日期范围 | "上周的日期范围是？" |
| `get_week_number` | 获取周数信息 | "12月5号是第几周？" |

示例实现：

```python
@tool(
    "get_current_time",
    "Get the current date and time...",
    {}
)
async def get_current_time(args: dict[str, Any]):
    now = datetime.now()
    today = now.date()

    # 计算本周信息
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    # 计算本月第几周
    first_day = today.replace(day=1)
    week_of_month = (today.day + first_day.weekday()) // 7 + 1

    output = f"""**当前时间信息**
- **今天**: {today} ({['周一','周二','周三','周四','周五','周六','周日'][today.weekday()]})
- **本周**: {week_start} ~ {week_end}
- **本月第**: {week_of_month} 周
"""
    return {"content": [{"type": "text", "text": output}]}
```

#### GitLab 工具 (3 个)

| 工具名 | 功能 |
|--------|------|
| `get_gitlab_user_activity` | 获取用户活动（提交、MR、Issue） |
| `get_gitlab_issue_details` | 获取 Issue 详情 |
| `get_gitlab_mr_details` | 获取 MR 详情 |

#### Jira 工具 (3 个)

| 工具名 | 功能 |
|--------|------|
| `get_jira_user_activity` | 获取用户活动（Issue、工时） |
| `get_jira_worklog_summary` | 按项目统计工时 |
| `get_jira_issue_details` | 获取 Issue 详情 |

#### 报告工具 (8 个)

| 工具名 | 功能 |
|--------|------|
| `read_weekly_report` | 读取成员周报 |
| `update_weekly_report` | 更新成员周报 |
| `generate_weekly_report` | 从 GitLab/Jira 自动生成周报 |
| `add_personal_summary` | 添加个人总结 |
| `organize_weekly_report` | 整理原始周报到标准结构 |
| `read_month_report` | 读取整月报告 |
| `list_reports` | 列出所有报告 |
| `update_team_summary` | 更新团队总结 |

### 4.4 工具模式：依赖注入

```python
# tools/report_tools.py
def create_report_tools(report_manager, report_generator, config):
    """
    工厂函数模式：
    - 接收外部依赖（manager, generator, config）
    - 返回工具列表
    """

    @tool("read_weekly_report", "...", {...})
    async def read_weekly_report(args: dict[str, Any]):
        # 使用注入的 report_manager
        content = report_manager.read_report(year, month)
        ...

    @tool("generate_weekly_report", "...", {...})
    async def generate_weekly_report(args: dict[str, Any]):
        # 使用注入的 report_generator
        report = await report_generator.generate_member_weekly_report(...)
        ...

    return [read_weekly_report, generate_weekly_report, ...]
```

主程序中注入依赖：

```python
# main.py
self.tools = []
self.tools.extend(create_time_tools())  # 无依赖
self.tools.extend(create_report_tools(
    self.report_manager,      # 注入依赖
    self.report_generator,    # 注入依赖
    self.config               # 注入配置
))
self.tools.extend(create_gitlab_tools(self.gitlab_client))
self.tools.extend(create_jira_tools(self.jira_client))
```

### 4.5 System Prompt 设计

System Prompt 是 Agent 的"灵魂"，定义了其行为和能力边界：

```python
system_prompt = """你是 DevTeam Agent，一个专业的团队工作管理助手。

## 周报结构

周报采用以下 Markdown 结构：
```
# 年月团队周报
# 第N周 MM.DD-MM.DD
## 待整理周报
## 本周团队重点工作总结
## 成员名
### 本周工作总结
#### 🤖 Agent 总结
#### 个人总结
#### 工作明细
```

## 周报生成规则

当你使用 `generate_weekly_report` 工具生成周报后，你必须：
1. **仔细分析**获取到的所有工作明细
2. **撰写一段有意义的总结**，替换掉占位符
3. 使用 `update_weekly_report` 工具更新周报

## 个人总结示例

> 本周主要工作集中在**技术方案预研**方面，包括...

## 可用团队成员
{team_members}
"""
```

**设计要点**：

1. **明确角色定位**：告诉 Agent 它是谁
2. **定义数据结构**：说明周报的 Markdown 格式
3. **描述工作流程**：生成周报的步骤
4. **提供示例**：好的总结长什么样
5. **动态注入**：`{team_members}` 在运行时填充

### 4.6 双界面支持

#### CLI 模式

```python
# src/main.py
async def start(self):
    await self.client.connect()

    while True:
        user_input = input(f"\n[{self.turn_count + 1}] 你: ")

        if user_input.lower() == 'exit':
            break
        elif user_input.lower() == 'interrupt':
            await self.client.interrupt()
            continue
        elif user_input.lower() == 'new':
            await self.client.disconnect()
            await self.client.connect()
            continue

        await self.client.query(user_input)

        async for message in self.client.receive_response():
            # 处理响应...
```

#### Web 模式 (FastAPI + WebSocket)

```python
# src/web/app.py
@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    await agent_session.initialize()

    while True:
        data = await websocket.receive_text()
        message = json.loads(data)

        if message.get("type") == "message":
            await agent_session.client.query(message["content"])

            async for response in agent_session.client.receive_response():
                if isinstance(response, AssistantMessage):
                    for block in response.content:
                        if isinstance(block, TextBlock):
                            await websocket.send_json({
                                "type": "text",
                                "content": block.text
                            })
                        elif isinstance(block, ToolUseBlock):
                            await websocket.send_json({
                                "type": "tool_call",
                                "name": block.name
                            })
```

---

## 5. 项目迭代历程

### 版本演进

```
┌─────────────────────────────────────────────────────────────┐
│  v0.1 初始版本                                              │
│  - 基础 Agent 框架                                          │
│  - 简单的对话循环                                           │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│  v0.2 添加时间工具                                          │
│  - get_current_time                                         │
│  - get_date_range                                           │
│  - get_week_number                                          │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│  v0.3 完善报告功能                                          │
│  - 周报生成与管理工具                                       │
│  - GitLab/Jira 集成                                         │
│  - Markdown 解析器                                          │
│  - System Prompt 优化                                       │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│  v0.4 周报整理增强                                          │
│  - organize_weekly_report 工具                              │
│  - 支持从"待整理周报"自动整理                               │
│  - 内容解析与结构化                                         │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│  v0.5 Web 界面                                              │
│  - FastAPI + WebSocket                                      │
│  - 实时聊天界面                                             │
│  - 周报预览功能                                             │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│  v0.6 Bug 修复                                              │
│  - 团队周总结更新异常修复                                   │
└─────────────────────────────────────────────────────────────┘
```

### Git 提交历史

```
0a777f7 Merge pull request #1 - 修复团队周总结更新异常
0b342be 新增Web界面的方式使用agent
ef1fec6 更新周报管理逻辑，增强内容解析与整理功能
7e61d46 新增周报管理功能，完善报告生成与整理流程
35caf5f 更新报告管理逻辑，改进周报生成与维护功能
7a17bf5 新增 CLAUDE.md，完善项目开发指南
aa01009 新增时间操作工具模块 time_tools.py
2064a7c Initial commit
```

### 关键迭代点

#### 1. 时间感知能力

**问题**：Agent 不知道"今天"、"本周"是什么时候

**解决**：添加 `time_tools.py`，让 Agent 能够：
- 获取当前时间
- 计算日期范围
- 确定周数

#### 2. 周报结构标准化

**问题**：周报格式不统一，难以管理

**解决**：
- 定义标准 Markdown 结构
- 在 System Prompt 中明确说明
- 通过工具强制执行格式

#### 3. 原始周报整理

**问题**：团队成员提交的周报格式各异

**解决**：添加 `organize_weekly_report` 工具
- 从"待整理周报"段落读取原始内容
- 识别成员名称
- 自动整理到标准结构

#### 4. Web 界面

**问题**：CLI 不够友好，无法预览周报

**解决**：
- FastAPI 后端
- WebSocket 实时通信
- Markdown 渲染预览

---

## 6. 最佳实践与经验总结

### 6.1 工具设计原则

1. **单一职责**：每个工具只做一件事

```python
# 好 - 单一职责
@tool("get_user_activity", "获取用户活动", {...})
@tool("get_issue_details", "获取 Issue 详情", {...})

# 差 - 职责混杂
@tool("get_everything", "获取所有数据", {...})
```

2. **清晰的描述**：Claude 根据描述决定何时调用工具

```python
# 好 - 描述清晰
@tool(
    "get_date_range",
    "Calculate date range for periods like 'last week', 'this month', 'week N'",
    {...}
)

# 差 - 描述模糊
@tool("get_date", "获取日期", {...})
```

3. **友好的返回格式**：结果要易于理解

```python
# 好 - 格式化输出
return {
    "content": [{
        "type": "text",
        "text": f"""**用户活动摘要**
- 代码推送: {push_count} 次
- 合并请求: {mr_count} 个
- Jira 工时: {worklog_hours}h
"""
    }]
}
```

### 6.2 System Prompt 设计

1. **结构化**：使用标题、列表组织内容
2. **示例驱动**：提供好的输出示例
3. **边界清晰**：说明能做什么、不能做什么
4. **动态注入**：支持运行时配置

### 6.3 错误处理

```python
@tool("get_issue_details", "...", {...})
async def get_issue_details(args: dict[str, Any]):
    try:
        details = await client.get_issue(args["issue_id"])
        if not details:
            return {
                "content": [{
                    "type": "text",
                    "text": f"未找到 Issue #{args['issue_id']}"
                }]
            }
        # 正常处理...
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"获取 Issue 失败: {e}"
            }]
        }
```

### 6.4 异步编程

```python
# 好 - 异步操作
async def get_user_activity(args):
    gitlab_data = await gitlab_client.get_activity(...)  # 异步
    jira_data = await jira_client.get_activity(...)      # 异步
    return process(gitlab_data, jira_data)

# 更好 - 并行执行
async def get_user_activity(args):
    gitlab_task = gitlab_client.get_activity(...)
    jira_task = jira_client.get_activity(...)
    gitlab_data, jira_data = await asyncio.gather(gitlab_task, jira_task)
    return process(gitlab_data, jira_data)
```

### 6.5 配置管理

```python
@dataclass
class AgentConfig:
    gitlab: GitLabConfig
    jira: JiraConfig
    reports_dir: str
    team_members: list[str]

    @classmethod
    def from_env(cls) -> "AgentConfig":
        """从环境变量加载，支持默认值和验证"""
        gitlab = GitLabConfig.from_env()
        jira = JiraConfig.from_env()

        reports_dir = os.getenv("REPORTS_DIR", "data/reports")

        members_str = os.getenv("TEAM_MEMBERS")
        if not members_str:
            raise ValueError("TEAM_MEMBERS 环境变量未设置")

        return cls(
            gitlab=gitlab,
            jira=jira,
            reports_dir=reports_dir,
            team_members=[m.strip() for m in members_str.split(",")]
        )
```

---

## 总结

### Claude Agent SDK 核心要点

1. **@tool 装饰器**：定义工具的标准方式
2. **create_sdk_mcp_server**：创建 MCP 服务器
3. **ClaudeSDKClient**：管理对话会话
4. **流式响应**：实时处理 Agent 输出

### 开发流程

```
1. 定义工具 (@tool)
       ↓
2. 创建 MCP 服务器
       ↓
3. 配置 Agent (system_prompt, allowed_tools)
       ↓
4. 运行对话循环 (connect → query → receive_response)
```

### 关键成功因素

- **好的 System Prompt**：定义清晰的角色和行为
- **合理的工具设计**：单一职责、清晰描述
- **标准化的数据结构**：便于处理和存储
- **友好的用户体验**：实时反馈、错误提示

---

## 参考资源

- [Claude Agent SDK 文档](https://docs.anthropic.com/claude/docs/claude-agent-sdk)
- [MCP 协议规范](https://modelcontextprotocol.io/)
- [DevTeam Agent 源码](https://github.com/your-repo/devteam_agent)

---

*本文档基于 DevTeam Agent v0.1.0 编写*
