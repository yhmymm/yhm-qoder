# 研续 ResearchMemory

> 有课题记忆的科研阅读助手 —— 基于 Open Notebook + PowerContext 1.4.1

## 项目解决的问题

科研阅读中，用户的课题目标、已确认结论、未解决问题和下一步计划散落在不同聊天会话中。隔几天继续研究时，需要重新说明课题背景，AI 无法自动恢复进展。

**研续**通过接入 PowerContext 实现课题记忆的持久化保存与跨会话接续，让每次新对话都能直接恢复上次的研究状态。

## 核心功能

### 四类研究记忆
- **研究目标** (goal)：本阶段要解决什么问题
- **阅读结论** (conclusion)：从资料中确认的发现，区分有依据/假设/用户陈述
- **未解决问题** (open_question)：仍需探索的方向
- **下一步计划** (next_step)：接下来要做的具体任务

### 跨会话接续
新建会话时输入"继续上次研究"，系统从 PowerContext 读取当前记忆，恢复目标、结论、问题和计划。不依赖旧聊天记录。

### 带依据的阅读问答
普通问答时，除了资料上下文，还注入相关研究记忆。回复区分：资料说明了什么、课题此前确认了什么、本次模型建议什么。

### 组会报告生成
一键生成 Markdown 格式的研究进展报告，包含：
1. 当前研究目标与范围
2. 本次阅读材料及主要发现
3. 已确认的阶段进展
4. 待验证假设与未解决问题
5. 下一步计划
6. 引用清单（记忆引用 + 资料证据）

### 修订与遗忘
- ETag 乐观并发修订，保留历史版本
- 从主动记忆移除（遗忘），历史仍可追溯
- 已遗忘内容不再参与新会话接续

### 课题隔离
每个 Notebook 绑定独立的 PowerContext Scope，课题 A 的记忆不会被课题 B 召回。

## 架构

```
用户 → Open Notebook 前端 (Next.js/React, port 8502)
         ↓
     FastAPI 业务接口 (port 5055)
         ↓
     ┌───┴────────┐
     ↓            ↓
  原有服务      新增课题记忆服务
     ↓            ↓
  SurrealDB    PowerContext Server 1.4.1 (port 8001)
                 ↓
             SQLite (独立持久化)
```

### 关键设计决策
- **一个 Notebook = 一个 Scope**：课题隔离的最小粒度
- **业务 JSON 序列化为 text**：research-memory.v1 schema 存入 Atomic Memory 的 text 字段
- **不臆造 API/ID/ETag**：所有资源引用来自真实 PowerContext 响应
- **候选不自动成为记忆**：必须经用户逐条确认
- **记忆不进入聊天 checkpoint**：通过请求参数注入，不持久追加为消息

## 技术栈

| 组件 | 技术 | 版本 |
|---|---|---|
| 前端 | Next.js / React | 16.3.8 |
| 后端 | FastAPI / Python | 3.12 |
| 原有数据库 | SurrealDB | 2.2.1 |
| 记忆服务 | PowerContext Server | 1.4.1 |
| AI 框架 | LangChain / LangGraph | - |
| LLM | DeepSeek API (v4flash) | - |
| 部署 | Docker Compose | - |

## 开源复用

- **Open Notebook**：MIT License, Copyright 2024 Luis Novo。复用资料导入、笔记、聊天、前后端框架。源码固定版本 `a0f6f308` 纳入 `qoder/app/`。
- **PowerContext**：Apache License 2.0。作为独立 Server 通过 HTTP API 接入，不修改源码。

## 快速开始

```bash
# 1. 初始化
python qoder/scripts/bootstrap.py

# 2. 启动
docker compose --env-file qoder/deploy/.env -f qoder/deploy/compose.yaml up --build -d

# 3. 健康检查
python qoder/scripts/healthcheck.py

# 4. 导入演示数据
python qoder/scripts/seed_demo.py

# 5. 运行验收
python qoder/scripts/verify_acceptance.py
```

## 验收结果

```
Results: 19/19 checks passed
✓ All acceptance checks passed!
```

覆盖：健康检查、Scope 绑定、记忆确认、PowerContext 直接读取、跨会话接续、课题隔离、报告生成、修订与遗忘。

## 代码仓库

- 仓库：https://github.com/oceanbase/powercontext
- 分支：`feat/qoder`
- 起点 commit：`d647275c` (2026-competition-ecosystem)

## 开发记录

| 阶段 | 内容 | 状态 |
|---|---|---|
| M0 | 上游固定、PowerContext 探针 15 步 | ✅ |
| M1 | 课题绑定、手工记忆闭环 | ✅ |
| M2 | 跨会话接续、聊天集成 | ✅ |
| M3 | 模型抽取、ETag 修订、遗忘 | ✅ |
| M4 | 组会报告、引用校验、导出 | ✅ |
| M5 | Docker Compose、验收脚本 | ✅ |
| M6 | Qoder Sites 发布 | 🔄 |
