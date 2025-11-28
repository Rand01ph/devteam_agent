# DevTeam Agent

团队工作管理 Agent，基于 Claude Agent SDK 构建，集成 GitLab 和 Jira，自动生成和管理团队周报。

## 功能特性

- **周报管理**: 按月度存储的 Markdown 格式周报，组织结构为：月份 → 周 → 成员
- **GitLab 集成**: 自动获取团队成员的代码提交、合并请求、Issues 等活动
- **Jira 集成**: 自动获取团队成员的需求、任务处理情况
- **自动生成周报**: 基于 GitLab 和 Jira 的活动自动生成成员周报
- **智能总结**: 利用 Claude AI 总结团队周报和月报
- **Issue 详情扩展**: 周报中提到的 Issue 可以自动获取详细信息
- **对话式交互**: 通过自然语言与 Agent 交互，查询和管理周报

## 项目结构

```
devteam_agent/
├── src/
│   ├── config.py              # 配置管理
│   ├── main.py                # 主程序入口
│   ├── integrations/          # 第三方集成
│   │   ├── gitlab_client.py   # GitLab API 客户端
│   │   └── jira_client.py     # Jira API 客户端
│   ├── report/                # 报告管理
│   │   ├── markdown_manager.py  # Markdown 文件管理
│   │   └── generator.py         # 周报生成器
│   └── tools/                 # MCP 工具定义
│       ├── report_tools.py    # 周报管理工具
│       ├── gitlab_tools.py    # GitLab 工具
│       └── jira_tools.py      # Jira 工具
├── data/
│   └── reports/               # 周报存储目录
│       ├── 2025-01.md        # 按月存储
│       └── ...
├── .env                       # 环境变量配置（需自行创建）
├── .env.example               # 环境变量模板
└── pyproject.toml            # 项目配置
```

## 周报文件格式

每月一个 Markdown 文件（如 `2025-01.md`），格式如下：

```markdown
# 2025年1月团队周报

# 第1周

## 张三

### 本周工作总结

**代码提交**: 15 次提交
  - `abc12345` 修复登录bug - [查看](https://gitlab.../commit/abc12345)
  - ...

**合并请求**: 3 个 MR
  - ✅ !42 实现用户认证功能 - [查看](https://gitlab.../merge_requests/42)
  - ...

**Jira Issues**: 分配 5 个, 创建 2 个
  - ✨ ✅ [PROJ-123](https://jira.../PROJ-123) 实现新功能
  - ...

## 李四

...

# 第2周

...
```

## 安装配置

### 1. 安装依赖

```bash
# 使用 uv（推荐）
uv sync

# 或使用 pip
pip install -e .
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并填写配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```bash
# GitLab 配置
GITLAB_URL=https://gitlab.your-company.com
GITLAB_TOKEN=your_gitlab_personal_access_token
GITLAB_PROJECT_IDS=  # 可选，留空则跟踪所有项目

# Jira 配置
JIRA_URL=https://jira.your-company.com
JIRA_USERNAME=your_email@company.com
JIRA_API_TOKEN=your_jira_api_token
JIRA_PROJECT_KEYS=  # 可选，留空则跟踪所有项目

# 团队成员
TEAM_MEMBERS=张三,李四,王五
```

### 3. 获取 API Token

**GitLab Personal Access Token:**
1. 登录 GitLab
2. 访问 `Settings` → `Access Tokens`
3. 创建 token，权限需要：`read_api`, `read_repository`

**Jira API Token:**
1. 登录 Jira
2. 访问 `Account Settings` → `Security` → `API tokens`
3. 创建新的 API token

## 使用方法

### 启动 Agent

```bash
# 使用 uv
uv run python -m src.main

# 或直接运行
python -m src.main
```

### 命令交互

启动后，你可以通过自然语言与 Agent 交互：

**生成周报：**
```
生成张三本周的周报
```

**查看周报：**
```
查看本月所有周报
查看张三第1周的周报
```

**查看活动：**
```
查看李四在 GitLab 上的活动
查看王五在 Jira 上的任务
```

**总结报告：**
```
总结团队本周的工作
总结本月的工作情况
```

**查看详情：**
```
查看 PROJ-123 这个 issue 的详细信息
查看 GitLab issue #42 的详情
```

### Agent 可用工具

Agent 配备了以下工具：

**周报管理工具：**
- `read_weekly_report`: 读取成员周报
- `update_weekly_report`: 更新/创建周报
- `generate_weekly_report`: 自动生成周报（从 GitLab/Jira）
- `read_month_report`: 读取月度报告
- `list_reports`: 列出所有报告

**GitLab 工具：**
- `get_gitlab_user_activity`: 获取用户活动
- `get_gitlab_issue_details`: 获取 Issue 详情

**Jira 工具：**
- `get_jira_user_activity`: 获取用户活动
- `get_jira_issue_details`: 获取 Issue 详情

## 示例工作流

### 每周生成团队周报

```python
# 在 Agent 对话中：
"生成本周所有团队成员的周报，时间是 2025-01-06 到 2025-01-12"
```

Agent 会：
1. 自动为每个团队成员调用 GitLab 和 Jira API
2. 收集本周的活动数据
3. 格式化生成周报
4. 保存到对应的月度文件中

### 总结月度工作

```python
# 在 Agent 对话中：
"请总结 2025年1月 团队的工作情况"
```

Agent 会：
1. 读取 2025-01.md 文件
2. 分析所有周报内容
3. 生成月度总结报告

## 扩展功能

未来可以扩展的功能：

- [ ] 按业务方向维度总结
- [ ] 自定义时间维度总结
- [ ] 导出为其他格式（PDF、HTML）
- [ ] 可视化报表
- [ ] 自动发送周报邮件
- [ ] 集成更多项目管理工具

## 技术栈

- **Claude Agent SDK**: Agent 框架
- **httpx**: HTTP 客户端（异步）
- **python-dotenv**: 环境变量管理
- **GitLab API**: 代码管理集成
- **Jira REST API**: 需求管理集成

## 故障排查

**问题: 无法连接到 GitLab/Jira**
- 检查 URL 是否正确（不要遗漏 https://）
- 检查 token/API key 是否有效
- 检查网络连接和防火墙设置

**问题: 找不到用户活动**
- 确认用户名正确（GitLab 和 Jira 的用户名可能不同）
- 检查日期范围是否正确
- 确认用户在指定项目中有活动权限

**问题: 周报文件未生成**
- 检查 `REPORTS_DIR` 目录是否有写权限
- 查看错误日志

## License

MIT License