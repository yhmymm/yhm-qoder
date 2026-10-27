# 上游审计报告

版本：1.0  
审计日期：2026-10-27  
审计范围：Open Notebook `a0f6f30` + PowerContext `1.4.1`

## 1. 比赛分支与工作区状态

| 项目 | 结果 |
|---|---|
| 比赛分支 | `2026-competition-ecosystem` |
| 开发分支 | `feat/qoder` |
| 起点 commit | `d647275c` |
| 工作区状态 | 干净（无未提交修改） |
| qoder/ 目录 | 已创建，包含需求文档和脚本 |

## 2. Open Notebook 上游核对

### 2.1 源码导入

- 来源：`https://github.com/lfnovo/open-notebook`
- 固定 commit：`a0f6f3081ae06328f0a451b3a3ef2959ca25721d`（main 分支 HEAD）
- 导入位置：`qoder/app/`
- 许可证：MIT License (Copyright 2024 Luis Novo)
- 已保留：LICENSE、README.md、pyproject.toml、所有源码目录

### 2.2 关键文件核对

| 文件路径 | 状态 | 说明 |
|---|---|---|
| `api/main.py` | ✅ 存在 | FastAPI 应用入口 |
| `api/routers/chat.py` | ✅ 存在 | 聊天路由 |
| `open_notebook/graphs/chat.py` | ✅ 存在 | LangGraph 聊天图 |
| `open_notebook/domain/notebook.py` | ✅ 存在 | Notebook 领域模型 |
| `open_notebook/utils/context_builder.py` | ✅ 存在 | 上下文构建工具 |
| `frontend/src/lib/api/chat.ts` | ✅ 存在 | 前端聊天 API |
| `frontend/src/lib/hooks/use-notebook-chat.ts` | ✅ 存在 | 前端聊天 Hook |
| `frontend/package.json` | ✅ 存在 | Next.js/React 前端 |
| `docker-compose.yml` | ✅ 存在 | 含 SurrealDB 配置 |
| `Dockerfile` | ✅ 存在 | 应用构建 |
| `pyproject.toml` | ✅ 存在 | version=1.15.0, python>=3.11,<3.13 |
| `uv.lock` | ✅ 存在 | 依赖锁文件 |
| `open_notebook/database/migrations/` | ✅ 存在 | 数据库迁移目录 |

### 2.3 技术栈确认

| 组件 | 技术 | 版本 |
|---|---|---|
| 后端框架 | FastAPI | >=0.104.0 |
| 异步服务器 | uvicorn | >=0.24.0 |
| 数据模型 | Pydantic | >=2.9.2 |
| 日志 | loguru | >=0.7.2 |
| AI 框架 | LangChain | >=1.3.9,<2 |
| 数据库 | SurrealDB | 按 docker-compose.yml |
| 前端 | Next.js/React | 按 package.json |
| Python | 3.12 | .python-version |

### 2.4 原版运行状态

| 项目 | 状态 | 说明 |
|---|---|---|
| 源码导入 | ✅ 完成 | 无嵌套 .git |
| 依赖安装 | ⏳ 待 M0 完成 | 需要 uv sync + npm install |
| SurrealDB 启动 | ⏳ 待 M0 完成 | 需要 docker compose |
| 资料导入 | ⏳ 待 M0 完成 | 需要配置模型凭据 |
| 阅读问答 | ⏳ 待 M0 完成 | 端到端验证 |

## 3. PowerContext 1.4.1 核对

### 3.1 版本确认

| 项目 | 结果 |
|---|---|
| Python 包版本 | 1.4.1 ✅ |
| 源码 tag commit | `8ef4f645` = `powercontext-v1.4.1` ✅ |
| 与需求文档一致 | ✅ |

### 3.2 独立启动

| 项目 | 结果 |
|---|---|
| 安装方式 | `uv tool install "powercontext[cli,server]==1.4.1"` |
| 启动命令 | `powercontext server run --host 127.0.0.1 --port 8001 --role all` |
| 启动结果 | ✅ 成功 |
| 绑定地址 | 127.0.0.1:8001 |
| 存储后端 | SQLite（默认） |
| 推理模型 | 未配置（基础记忆无需） |
| 健康检查 | `/health/live` → `{"status":"ok"}` ✅ |
| 就绪检查 | `/health/ready` → `{"status":"ready"}` ✅ |

### 3.3 记忆探针结果（15 步全通过）

| 步骤 | 操作 | 结果 | 关键发现 |
|---|---|---|---|
| 1 | Health Check | ✅ | live=200, ready=200 |
| 2 | Create Scope | ✅ | 201, 返回 scope_id + version |
| 3 | Capture Content Source | ✅ | **202 Accepted**（非 201） |
| 4 | Create Atomic Memory | ✅ | 201, 返回 artifact_id, revision, ETag |
| 5 | Read Artifact Head | ✅ | 200, 返回 ETag header |
| 6 | List Atomic Memories | ✅ | 200, 分页 + next_cursor |
| 7 | Search Atomic Memories | ✅ | 200, mode=text 可用 |
| 8 | Replace Artifact | ✅ | 200, If-Match 修订, 新 revision + ETag |
| 9 | Precondition Failed | ✅ | **412** 正确拒绝过期 ETag |
| 10 | List Revisions | ✅ | 200, 返回 2 个 revision |
| 11 | Read Historical Revision | ✅ | 200, revision 1 内容完整 |
| 12 | Get Memory State | ✅ | 200, state=active, state_version=0 |
| 13 | Forget Memory | ✅ | 200, changed=true, state→forgotten |
| 14 | Verify Forgotten | ✅ | state=forgotten, state_version=1 |
| 15 | Active List Excludes Forgotten | ✅ | 0 items（已遗忘内容不在活跃列表） |

### 3.4 实际 API 契约要点

| 要点 | 说明 |
|---|---|
| Source 捕获 | POST /v1/sources/content 返回 **202 Accepted**（异步接受），非 201 |
| ETag | 不透明字符串，必须原样传递；不能用 revision 数字伪造 |
| If-Match | 修订时必须携带；缺失返回 428 Precondition Required |
| state_version | 初始为 0；状态变更时递增 |
| Lifecycle | 只支持 `forgotten` 一种目标状态 |
| Scope 创建 | 需要 title, summary, idempotency_key；返回 scope_id（服务端生成） |
| Atomic Memory 创建 | family="atomic-memory", content={schema, kind, text} |
| 分页 | list 和 search 都支持 next_cursor 分页，不能把第一页当全部 |
| 认证 | 当前未启用（access_mode=disabled）；生产部署需配置 token |
| 推理模型 | 基础 Atomic Memory 读写无需；Experience/Skill 等需要 |

### 3.5 与需求文档的差异

| 需求文档描述 | 实际行为 | 影响 |
|---|---|---|
| POST /v1/sources/content 返回 201 | 实际返回 202 | 低：适配层需接受 202 作为成功 |
| 需求文档提到 `add_memory(project_id=...)` | 不存在此 SDK 函数 | 无：使用 HTTP 接入 |
| 需求文档提到 ETag 为 revision 数字 | ETag 为不透明字符串 | 中：必须从响应头获取并原样传递 |

## 4. 已验证的接入位置

| 需求文档路径 | 实际状态 | 说明 |
|---|---|---|
| `api/main.py` | ✅ 存在 | 注册新 Router 的位置 |
| `api/routers/chat.py` | ✅ 存在 | 聊天路由，需在此加入研究上下文 |
| `open_notebook/graphs/chat.py` | ✅ 存在 | LangGraph 聊天图 |
| `frontend/src/lib/api/chat.ts` | ✅ 存在 | 前端聊天 API 调用 |
| `frontend/src/lib/hooks/use-notebook-chat.ts` | ✅ 存在 | 前端聊天 Hook |
| `open_notebook/database/migrations/` | ✅ 存在 | 新增迁移的位置 |

## 5. 待完成项

| 项目 | 状态 | 阻塞原因 |
|---|---|---|
| Open Notebook 原版运行 | ⏳ 待完成 | 需要 Docker + SurrealDB + 模型凭据 |
| 前端 npm install | ⏳ 待完成 | 需要 Node.js 环境 |
| 端到端阅读问答 | ⏳ 待完成 | 依赖上述步骤 |

## 6. 结论

- PowerContext 1.4.1 独立运行正常，记忆探针 15 步全部通过
- Open Notebook 源码已完整导入，关键文件位置已核对
- 实际 API 契约与需求文档基本一致，有少量差异已记录
- M0 阶段门槛条件部分满足：PowerContext 探针 ✅，原版运行 ⏳
