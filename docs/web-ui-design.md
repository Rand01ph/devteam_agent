# DevTeam Agent Web UI 设计文档

## 一、需求概述

为 DevTeam Agent 添加简单的 Web 界面，支持：
1. 与 Agent 对话交互
2. 查看和浏览 `data/reports/` 下的 Markdown 周报

## 二、技术方案

### 技术选型

| 组件 | 选择 | 理由 |
|------|------|------|
| 后端 | FastAPI | 轻量、支持 async、WebSocket 原生支持 |
| 前端 | 原生 HTML + Tailwind CSS + HTMX | 简单、无需构建工具、交互体验好 |
| Markdown 渲染 | marked.js（前端） | 纯前端渲染，实时预览 |
| 通信 | WebSocket | 支持流式响应，实时显示 Agent 回复 |

### 备选方案

如果觉得 FastAPI + HTMX 还是复杂，可以选择：
- **Gradio**：一行代码搭建聊天界面，但自定义能力较弱
- **Streamlit**：简单快速，但布局受限

## 三、界面设计

### 布局方案：左右分栏

```
+------------------------------------------+
|             DevTeam Agent                |
+------------------------------------------+
|          |                               |
|  周报列表 |         主区域                |
|          |   (对话 / Markdown预览)       |
|  2025-12 |                               |
|  2025-11 |                               |
|          |                               |
+----------+-------------------------------+
```

### 页面组成

#### 1. 左侧边栏 (~200px)
- 周报文件列表（按时间倒序）
- 点击切换到 Markdown 预览
- 底部：返回对话按钮

#### 2. 主区域

**对话模式：**
```
+--------------------------------+
|  对话历史区域                   |
|  [User]: 生成本周周报           |
|  [Agent]: 🔧 调用工具...        |
|  [Agent]: 周报已生成...         |
|                                |
+--------------------------------+
|  输入框                  [发送] |
+--------------------------------+
```

**Markdown 预览模式：**
```
+--------------------------------+
|  📄 2025-12.md        [返回对话]|
+--------------------------------+
|                                |
|  # 第1周 12.1-12.7             |
|  ## 本周团队重点工作总结        |
|  ...                           |
|                                |
+--------------------------------+
```

## 四、核心功能

### 4.1 对话功能

- 输入消息发送给 Agent
- 流式显示 Agent 回复（通过 WebSocket）
- 显示工具调用状态（如 `🔧 调用工具: generate_weekly_report`）
- 支持中断当前任务

### 4.2 周报浏览

- 列出 `data/reports/*.md` 文件
- 点击文件名，在主区域渲染 Markdown
- 支持目录内跳转（锚点定位）

### 4.3 实时更新

- Agent 生成/更新周报后，自动刷新文件列表
- 当前预览的文件被修改时，自动重新加载

## 五、目录结构

```
src/
├── main.py              # 现有 CLI 入口
├── web/                 # 新增 Web 模块
│   ├── __init__.py
│   ├── app.py           # FastAPI 应用
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── chat.py      # 对话 WebSocket
│   │   └── reports.py   # 周报 API
│   ├── static/
│   │   ├── style.css    # Tailwind 样式
│   │   └── app.js       # 前端逻辑
│   └── templates/
│       └── index.html   # 主页面模板
```

## 六、API 设计

### 6.1 WebSocket 对话接口

```
WS /ws/chat

# 客户端发送
{ "type": "message", "content": "生成本周周报" }
{ "type": "interrupt" }
{ "type": "new_session" }

# 服务端响应
{ "type": "text", "content": "正在处理..." }
{ "type": "tool_call", "name": "generate_weekly_report" }
{ "type": "thinking" }
{ "type": "done", "duration_ms": 5000 }
{ "type": "error", "message": "..." }
```

### 6.2 REST API

```
GET  /api/reports           # 获取周报文件列表
GET  /api/reports/{name}    # 获取周报内容 (原始 Markdown)
```

## 七、依赖新增

```toml
# pyproject.toml 新增
dependencies = [
    # ... 现有依赖
    "fastapi>=0.115.0",
    "uvicorn>=0.32.0",
    "jinja2>=3.1.0",
]
```

## 八、启动方式

```bash
# CLI 模式（现有）
uv run python -m src.main

# Web 模式（新增）
uv run python -m src.web
# 或
uv run uvicorn src.web.app:app --reload
```

## 九、开发步骤

1. 添加依赖并安装
2. 创建 `src/web/` 目录结构
3. 实现 FastAPI 应用基础框架
4. 实现周报列表和预览功能
5. 实现 WebSocket 对话功能
6. 集成现有 `DevTeamAgent` 类
7. 编写前端页面和样式
8. 测试和调试

## 十、待确认问题

1. **会话持久化**：是否需要保存对话历史？
2. **多用户支持**：是否需要支持多人同时使用？
3. **认证**：是否需要登录功能？
4. **部署方式**：本地运行还是需要部署到服务器？

---

以上是初步设计方案，请确认是否满足需求，或有其他调整意见。
