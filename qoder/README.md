# 研续 ResearchMemory

> 有课题记忆的科研阅读助手

## 项目简介

研续（ResearchMemory）是一个基于 Open Notebook 二次开发的科研阅读助手，通过接入 PowerContext 实现课题记忆的持久化与跨会话接续。

**解决的核心问题**：阅读资料散落在不同会话中，用户隔几天继续研究时需要重新说明课题目标、已确认结论和未解决问题。研续让用户的课题进展被持久化保存，新会话可以直接恢复。

## 核心功能

- **课题 Scope 绑定**：一个 Notebook 对应一个研究课题，绑定一个 PowerContext Scope
- **四类研究记忆**：研究目标、阅读结论、未解决问题、下一步计划
- **手工/模型录入**：支持手工填写和从资料中模型提取记忆候选
- **用户确认写入**：候选经用户逐条确认后才实际写入 PowerContext
- **修订与遗忘**：支持 ETag 乐观并发修订和从主动召回中移除
- **跨会话接续**：新会话从 PowerContext 读取当前记忆，恢复课题进展
- **带依据的问答**：资料上下文 + 研究记忆，区分事实、假设和建议
- **组会报告**：生成带真实引用的 Markdown 报告

## 架构

```
用户 → Open Notebook 前端 (Next.js/React)
         ↓
     FastAPI 业务接口
         ↓
     ┌───┴───┐
     ↓       ↓
  原有服务  新增课题记忆服务
     ↓       ↓
  SurrealDB  PowerContext Server (HTTP)
               ↓
           SQLite (独立存储)
```

## 技术栈

| 组件 | 技术 |
|---|---|
| 前端 | Next.js / React |
| 后端 | FastAPI / Python 3.12 |
| 原有数据库 | SurrealDB |
| 记忆服务 | PowerContext 1.4.1 (独立 Server) |
| 记忆存储 | SQLite (PowerContext 内置) |
| AI 框架 | LangChain / LangGraph |

## 运行说明

### 前置条件

- Docker 与 Docker Compose
- Python 3.12
- Node.js 18+
- 可用的 LLM API Key（如 OpenAI）
- 可用的 Embedding 模型配置

### 快速启动

```bash
# 1. 初始化配置
python qoder/scripts/bootstrap.py

# 2. 启动服务
docker compose --env-file qoder/deploy/.env -f qoder/deploy/compose.yaml up --build -d

# 3. 健康检查
python qoder/scripts/healthcheck.py

# 4. 导入演示数据
python qoder/scripts/seed_demo.py

# 5. 运行验收
python qoder/scripts/verify_acceptance.py
```

### 服务地址

| 服务 | 地址 |
|---|---|
| Open Notebook UI | http://127.0.0.1:8502 |
| Open Notebook API | http://127.0.0.1:5055 |
| PowerContext | http://127.0.0.1:8001（调试用） |

## 验证样例

详见 `qoder/docs/verification.md`（待创建）。

标准演示步骤覆盖 12 个场景：课题创建、资料导入、记忆确认、跨会话接续、修订、遗忘、跨课题隔离、报告生成、重启持久化、服务中断恢复。

## 项目结构

```
qoder/
├── README.md              # 本文件
├── UPSTREAM.md            # 上游复用说明
├── app/                   # Open Notebook 修改版源码
├── deploy/                # 部署配置
│   ├── compose.yaml       # Docker Compose
│   ├── powercontext/      # PowerContext 配置
│   └── .env.example       # 环境变量模板
├── docs/                  # 文档
│   ├── versions.md        # 版本固定清单
│   ├── upstream-audit.md  # 上游审计报告
│   └── tasks.md           # 分阶段任务清单
├── examples/              # 演示资料
├── scripts/               # 脚本
│   ├── bootstrap.py       # 初始化
│   ├── healthcheck.py     # 健康检查
│   ├── seed_demo.py       # 种子数据
│   ├── verify_acceptance.py # 验收脚本
│   └── probe_powercontext.py # PowerContext 探针
├── site/                  # Qoder Sites 网站资产
└── ResearchMemory_Qoder_Requirements.md # 需求文档
```

## 开源复用声明

- **Open Notebook**：MIT License, Copyright 2024 Luis Novo。复用资料导入、笔记、聊天、前后端框架。改造点见 UPSTREAM.md。
- **PowerContext**：Apache License 2.0。作为独立 Server 接入，不修改源码。
- 本项目新增部分遵循相同许可证。

## 比赛信息

- 赛题：Qoder × OceanBase - Build with Qoder
- 项目名：研续 ResearchMemory
- 比赛分支：`2026-competition-ecosystem`
- 起点 commit：`d647275c`

## 当前状态

🔄 **M0 进行中**：PowerContext 1.4.1 探针 15 步全通过，Open Notebook 原版运行待完成。

## 相关链接

- 项目网站：（待 Qoder Sites 发布后填写）
- 代码仓库：https://github.com/oceanbase/powercontext/tree/feat/qoder
- Qoder UID：（待填写）
