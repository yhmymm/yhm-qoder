# 上游复用说明

## Open Notebook

- 来源：https://github.com/lfnovo/open-notebook
- 固定 commit：`a0f6f3081ae06328f0a451b3a3ef2959ca25721d`
- 许可证：MIT License (Copyright 2024 Luis Novo)
- 许可证文件位置：`qoder/app/LICENSE`
- 复用范围：
  - 资料导入与文本解析
  - 笔记管理
  - 聊天会话与检查点
  - 资料上下文组装与检索
  - 模型配置与调用
  - 前后端框架（Next.js/React + FastAPI + SurrealDB）
- 改造位置：`qoder/app/` 内的修改通过 git diff 与上游对比
- 改造列表：
  - 新增 `api/routers/research.py`（研究功能路由）
  - 新增 `open_notebook/research/` 目录（课题记忆服务）
  - 修改 `api/main.py`（注册研究 Router）
  - 修改 `api/routers/chat.py`（接入研究上下文）
  - 修改 `open_notebook/graphs/chat.py`（注入研究记忆）
  - 新增前端组件 `frontend/src/components/research/`
  - 新增数据库迁移

## PowerContext

- 来源：https://github.com/oceanbase/powercontext
- 固定版本：Python 包 1.4.1
- 固定源码 commit：`8ef4f645e66622e223cd49720d5f009f63ecff85`（tag `powercontext-v1.4.1`）
- 许可证：Apache License 2.0
- 复用范围：
  - 独立运行的 PowerContext Server
  - Atomic Memory 读写与检索
  - Scope 管理
  - Source 捕获
  - 生命周期管理（遗忘）
  - 修订历史
- 接入方式：HTTP API（httpx.AsyncClient）
- 不修改 PowerContext 源码

## 比赛仓库

- 来源：https://github.com/oceanbase/powercontext
- 比赛分支：`2026-competition-ecosystem`
- 起点 commit：`d647275c`
