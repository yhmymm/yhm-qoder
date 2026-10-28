# 研续 ResearchMemory

> 有课题记忆的科研阅读助手

基于 Open Notebook + PowerContext 1.4.1 的科研阅读助手，实现课题记忆持久化与跨会话接续。

![19/19 验收通过](https://img.shields.io/badge/验收-19/19-green)
![M0-M6 全阶段完成](https://img.shields.io/badge/阶段-M0--M6-green)
![Python 3.12](https://img.shields.io/badge/Python-3.12-blue)
![Next.js 16](https://img.shields.io/badge/Next.js-16-blue)

## 项目简介

研续（ResearchMemory）是一个为科研阅读场景设计的 AI 助手，通过接入 PowerContext 记忆服务，实现课题目标的持久化保存与跨会话智能接续。

### 三大核心能力

- **🧠 持久化记忆** — 研究目标、结论、问题和计划存储在 PowerContext 中，不依赖聊天历史，关闭浏览器后依然存在
- **🔄 跨会话接续** — 新建对话时自动恢复上次研究状态，输入"继续上次研究"即可无缝衔接，无需重复说明背景
- **🔒 课题隔离** — 每个 Notebook 绑定独立 Scope，课题 A 的记忆不会被课题 B 召回，确保研究上下文不混淆

## 解决的问题

科研阅读中，课题目标、已确认结论、未解决问题和下一步计划**散落在不同聊天会话**中。隔几天继续研究时，需要重新说明课题背景，AI 无法自动恢复进展。多课题并行时，不同课题的信息更容易混淆。

**研续**通过 PowerContext 实现课题记忆的**持久化保存与跨会话接续**。四类结构化记忆（目标/结论/问题/计划）独立存储，每次新对话自动恢复研究状态，不依赖旧聊天记录。

## 核心功能

### 1. 🎯 四类研究记忆

| 类型 | 标识 | 说明 |
|------|------|------|
| 研究目标 | `goal` | 本阶段要解决什么问题 |
| 阅读结论 | `conclusion` | 区分有依据/假设/用户陈述 |
| 未解决问题 | `open_question` | 仍需探索的方向 |
| 下一步计划 | `next_step` | 具体待办任务 |

### 2. 🔄 跨会话接续

新建会话时输入"继续上次研究"，系统从 PowerContext 读取记忆，自动恢复目标、结论、问题和计划。不依赖旧聊天记录。

### 3. 📎 带依据的阅读问答

注入资料上下文 + 研究记忆，回复区分：
- **资料说了什么** — 基于导入的 PDF/文档原文
- **课题确认了什么** — 基于已确认的研究记忆
- **模型建议什么** — 基于 LLM 推理的补充建议

### 4.  组会报告生成

一键生成 Markdown 研究报告，包含六部分：
1. 研究目标与范围
2. 主要材料与发现
3. 阶段进展总结
4. 假设与未解决问题
5. 下一步计划
6. 引用清单（关联真实记忆 ID 和资料来源）

### 5. ✏️ 修订与遗忘

- ETag 乐观并发修订，保留历史版本
- 从主动记忆移除（遗忘），历史可追溯
- 已遗忘内容不再参与新会话接续

### 6. 🔒 课题隔离

每个 Notebook 绑定独立 PowerContext Scope，课题 A 的记忆不会被课题 B 召回。最小粒度的课题隔离。

## 界面演示

### 课题管理

![课题管理](yhm-qoder/qoder/site/image/feature1-notebook-list.png)

左侧导航栏包含 Sources、Notebooks、Ask & Search、Models 四个模块。右侧 Notebook 卡片网格展示所有研究课题，每个 Notebook 绑定独立的 PowerContext Scope。

### 跨会话接续

![跨会话接续](site/image/feature2-cross-session.png)

在 Chat 面板发送「继续上次研究」，系统自动从 PowerContext 读取 [M1]-[M4] 研究记忆，无缝衔接上次研究进度。

### 研究记忆管理

![研究记忆管理](site/image/feature3-memory-confirmation1.png)

在 Notebook 详情页点击「研究记忆」按钮，显示所有研究记忆（类型标签、内容摘要、版本号），支持修订和遗忘操作。

### 候选记忆确认

![候选记忆确认](site/image/feature3-memory-confirmation2.png)

点击「提取候选记忆」，LLM 从资料中自动抽取结构化候选记忆。用户逐条确认、修订后确认或拒绝，候选不会自动成为正式记忆。

### 提问与搜索

![提问界面](site/image/feature4-evidence-qa1.png)

在「提问与搜索」页面选择「提问 (beta)」标签，输入问题，系统展示推理过程和搜索词策略，支持选择 Notebook 范围和模型配置。

### 独立回答

![独立回答](site/image/feature4-evidence-qa2.png)

AI 生成的结构化回答，嵌入引用标注（如 `[source_insight:xxx]`、`[note:xxx]`），点击引用可查看原始资料或记忆详情。

### 最终回答

![最终回答](site/image/feature4-evidence-qa3.png)

Markdown 格式的结构化总结，引用真实资料来源，内容基于知识库文档生成，兼具学术严谨性与可读性。

### 知识库搜索

![知识库搜索](site/image/feature4-evidence-qa4.png)

支持文本搜索和向量搜索两种模式，可限定搜索范围（来源、笔记），结果按相关度排序。

### 组会报告生成

![组会报告](site/image/feature5-report.png)

一键生成六段式 Markdown 研究报告，所有引用均关联到真实的记忆 ID 和资料来源，支持保存为 Notebook 笔记。

### 修订与遗忘

![修订与遗忘](site/image/feature6-memory-revision.png)

支持 ETag 乐观并发修订，保留完整历史版本。可从主动记忆中移除（遗忘）条目，底部显示 ETag 版本信息确保并发安全。

## 系统架构

```
用户 → Open Notebook 前端
         (Next.js / React, port 3000)
         ↓
     FastAPI 业务接口 (port 5055)
         ↓
     ┌───┴────────────┐
     ↓                ↓
  原有服务          新增课题记忆服务
     ↓                ↓
  SurrealDB        PowerContext Server
  (port 8000)        1.4.1 (port 8001)
                       ↓
                   SQLite (独立持久化)
```

### 关键设计决策

- **一个 Notebook = 一个 Scope** — 课题隔离的最小粒度
- **业务 JSON 序列化为 text** — `research-memory.v1` schema 存入 Atomic Memory
- **不臆造 API / ID / ETag** — 所有引用来自真实 PowerContext 响应
- **候选不自动成为记忆** — 必须经用户逐条确认
- **记忆不进入聊天 checkpoint** — 通过请求参数注入，不持久追加为消息

## 技术栈

| 组件 | 技术 | 版本 |
|------|------|------|
| 前端 | Next.js / React | 16.3.8 |
| 后端 | FastAPI / Python | 3.12 |
| 原有数据库 | SurrealDB | 2.2.1 |
| 记忆服务 | PowerContext Server | 1.4.1 |
| AI 框架 | LangChain / LangGraph | — |
| LLM | DeepSeek API (v4flash) | — |
| 部署 | Docker Compose | — |

## 快速开始

### 前置要求

- Python 3.11+（推荐 3.12）
- Node.js 18.18+（前端需要）
- Docker & Docker Compose
- LLM API Key（如 DeepSeek）

### 启动步骤

```bash
# 1. 克隆仓库并进入项目目录
git clone https://github.com/oceanbase/powercontext.git
cd powercontext && git checkout feat/qoder

# 2. 初始化环境（安装依赖、配置服务）
python qoder/scripts/bootstrap.py

# 3. 启动全部服务（SurrealDB + PowerContext + Open Notebook）
docker compose --env-file qoder/deploy/.env \
           -f qoder/deploy/compose.yaml up --build -d

# 4. 健康检查 + 导入演示数据
python qoder/scripts/healthcheck.py
python qoder/scripts/seed_demo.py

# 5. 运行验收测试（19 项检查）
python qoder/scripts/verify_acceptance.py
```

### 服务端口

| 服务 | 地址 |
|------|------|
| 前端界面 | http://localhost:3000 |
| API 服务 | http://localhost:5055 |
| PowerContext | http://localhost:8001 |
| SurrealDB | http://localhost:8000 |

## 验收结果

**19 / 19 — All acceptance checks passed ✓**

| # | 检查项 | 说明 |
|---|--------|------|
| 1 | 服务健康检查（4 项） | SurrealDB / PowerContext / API / Frontend |
| 2 | Notebook ↔ Scope 绑定 | 每个 Notebook 正确绑定独立 Scope |
| 3 | 记忆创建与确认 | 候选提取、用户确认、写入 PowerContext |
| 4 | PowerContext 直接读取验证 | 绕过业务层直接验证存储 |
| 5 | 跨会话接续上下文注入 | 新会话正确恢复研究记忆 |
| 6 | 课题隔离（A ≠ B） | 课题 A 的记忆不会被课题 B 召回 |
| 7 | 报告生成与引用校验 | 六段式报告 + 引用完整性 |
| 8 | ETag 修订与遗忘机制 | 乐观并发 + 遗忘后不再参与接续 |

## 开发历程

从上游固定到发布上线，7 个阶段递进交付，全程在 Qoder IDE 中完成。

| 阶段 | 内容 | 状态 |
|------|------|------|
| **M0** — 上游固定与探针 | 固定 Open Notebook 源码版本 (a0f6f308)，安装 PowerContext 1.4.1，完成 15 步记忆 API 探针 | ✅ |
| **M1** — 课题绑定与手工记忆闭环 | Notebook ↔ Scope 绑定，手动创建/读取/修订 Atomic Memory，验证完整生命周期 | ✅ |
| **M2** — 跨会话接续与聊天集成 | 上下文组装（12000 字节预算）、[M编号]记忆引用、系统提示词注入，DeepSeek 正确接续 | ✅ |
| **M3** — 模型抽取、ETag 修订与遗忘 | LLM 从资料中抽取结构化候选，乐观并发修订，遗忘机制，证据编号校验 | ✅ |
| **M4** — 组会报告、引用校验与导出 | 6 段式 Markdown 报告生成，引用清单完整性校验，保存为 Notebook 笔记 | ✅ |
| **M5** — Docker Compose 与验收脚本 | 3 服务编排（SurrealDB + PowerContext + Open Notebook），19 项自动化验收全通过 | ✅ |
| **M6** — 项目网站与 Qoder Sites 发布 | 项目展示网站构建，通过 Qoder Sites 发布为公开可访问站点 | ✅ |

## 项目结构

```
qoder/
├── README.md                  # 本文件
├── UPSTREAM.md                # 上游复用说明
├── app/                       # Open Notebook 修改版源码
│   ├── frontend/              # Next.js 前端
│   │   ├── src/
│   │   │   ├── components/
│   │   │   │   ├── research/  # 研究记忆组件
│   │   │   │   │   └── ResearchMemoryPanel.tsx
│   │   │   │   ├── sources/   # Chat 面板（集成研究记忆按钮）
│   │   │   │   └── search/    # 流式响应（引用渲染修复）
│   │   │   └── lib/
│   │   │       └── hooks/
│   │   │           └── use-research-memory.ts
│   │   └── open_notebook/     # 后端图逻辑
│   │       └── graphs/
│   │           └── source.py  # PDF 文本提取改进
│   ── ...
├── deploy/                    # 部署配置
│   ├── compose.yaml           # Docker Compose
│   ├── powercontext/          # PowerContext 配置
│   └── .env.example           # 环境变量模板
├── scripts/                   # 脚本
│   ├── bootstrap.py           # 初始化
│   ├── healthcheck.py         # 健康检查
│   ├── seed_demo.py           # 种子数据
│   ── verify_acceptance.py   # 验收脚本（19 项）
└── site/                      # 项目展示网站
    ├── index.html             # 单页展示站
    └── image/                 # 功能截图（10 张）
```

## 开源复用声明

| 项目 | 许可证 | 复用方式 |
|------|--------|----------|
| **Open Notebook** | MIT License (Copyright 2024 Luis Novo) | 复用资料导入、笔记、聊天、前后端框架。源码固定版本 `a0f6f308` 纳入 `qoder/app/` |
| **PowerContext** | Apache License 2.0 | 作为独立 Server 通过 HTTP API 接入，不修改源码。版本 1.4.1 |

本项目新增部分遵循相同许可证。

## 相关链接

- **代码仓库**：https://github.com/yhmymm/yhm-qoder
- **上游仓库**：https://github.com/oceanbase/powercontext
- **比赛分支**：`2026-competition-ecosystem`
- **起点 commit**：`d647275c`
