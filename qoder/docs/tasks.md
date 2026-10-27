# 分阶段任务清单

版本：1.0  
更新日期：2026-10-27  
基准分支：`2026-competition-ecosystem` @ `d647275c`

---

## M0 固定上游与跑通原版

### 已完成

- [x] 检查比赛分支 `2026-competition-ecosystem`，记录起点 commit `d647275c`
- [x] 创建开发分支 `feat/qoder`
- [x] 导入 Open Notebook `a0f6f30` 到 `qoder/app/`，保留 LICENSE
- [x] 核对关键文件路径（api/main.py, chat.py, graphs/chat.py 等）
- [x] 安装 PowerContext 1.4.1（`uv tool install`）
- [x] 独立启动 PowerContext Server（127.0.0.1:8001）
- [x] 跑通记忆探针 15 步（Scope → Source → Create → Read → List → Search → Replace → 412 → Revisions → Forget → Verify）
- [x] 生成 versions.md、upstream-audit.md

### 待完成

- [ ] 安装 Docker 并启动 SurrealDB
- [ ] 安装 Open Notebook 后端依赖（`uv sync`）
- [ ] 安装前端依赖（`npm install`）
- [ ] 配置模型凭据（需要用户提供 API Key）
- [ ] 启动原版 Open Notebook
- [ ] 导入一份公开文本资料，完成一次阅读问答
- [ ] 记录原版运行结果

### 阻塞项

| 阻塞 | 说明 | 需要用户操作 |
|---|---|---|
| Docker | 需要 Docker 环境运行 SurrealDB | 确认 Docker 可用或安装 |
| 模型凭据 | Open Notebook 需要 LLM 和 Embedding 模型 | 提供 API Key 或本地模型配置 |

---

## M1 课题绑定与手工记忆闭环

### 任务

- [ ] 实现数据库迁移：新增 research_scope_binding, research_memory_draft, research_memory_link, research_memory_operation, research_trace, research_report
- [ ] 实现 PowerContext HTTP 适配层（`open_notebook/research/powercontext_client.py`）
  - [ ] create_scope
  - [ ] capture_content_source
  - [ ] create_artifact (atomic-memory)
  - [ ] get_artifact (含 ETag)
  - [ ] replace_artifact (含 If-Match)
  - [ ] list_atomic_memories
  - [ ] search_atomic_memory
  - [ ] change_atomic_memory_lifecycle (forget)
  - [ ] get_atomic_memory_state
  - [ ] get_artifact_revision
- [ ] 实现 Scope 绑定服务（`open_notebook/research/memory_service.py`）
  - [ ] enable_research_scope（幂等创建）
  - [ ] 部署 UUID 生成与持久化
- [ ] 实现记忆草稿模型（`open_notebook/research/models.py`）
  - [ ] 四类记忆类型校验
  - [ ] 业务 JSON 结构校验
  - [ ] NFC + 8192 UTF-8 字节限制
- [ ] 实现手工录入 API
  - [ ] POST /api/research/notebooks/{id}/enable
  - [ ] POST /api/research/notebooks/{id}/memory-drafts (mode=manual)
  - [ ] PUT /api/research/notebooks/{id}/memory-drafts/{draft_id}
  - [ ] POST /api/research/notebooks/{id}/memory-confirmations
  - [ ] GET /api/research/notebooks/{id}/memories
  - [ ] GET /api/research/notebooks/{id}/memories/{item_id}
- [ ] 实现操作记录与去重
  - [ ] operation_id 唯一约束
  - [ ] 请求指纹
  - [ ] 状态条件更新
- [ ] 前端最小记忆卡片
  - [ ] 记忆候选列表
  - [ ] 手工录入表单
  - [ ] 确认按钮（逐条选中）
  - [ ] 状态显示：草稿/确认中/已保存/失败/待核实

### 验收

- [ ] 新建课题，确认四类记忆
- [ ] 在 PowerContext 独立读取确认记忆
- [ ] 重启后仍存在
- [ ] 重复点击不会重复创建
- [ ] 写入失败不显示成功

---

## M2 跨会话接续与原文证据

### 任务

- [ ] 实现研究上下文服务（`open_notebook/research/context_service.py`）
  - [ ] 当前状态读取（goal + 未完成 open_question + next_step）
  - [ ] 相关检索（mode=text）
  - [ ] 证据取回与校验
  - [ ] 预算控制（12000 UTF-8 字节）
  - [ ] 编号分配（M 编号 + S 编号）
  - [ ] trace 记录
- [ ] 实现接续 API
  - [ ] POST /api/research/notebooks/{id}/resume
  - [ ] 新建真实聊天会话
  - [ ] 从 PowerContext 读取当前记忆
  - [ ] 组装上下文注入模型 payload
- [ ] 接入聊天流程
  - [ ] 修改 api/routers/chat.py 注册研究 Router
  - [ ] 修改 open_notebook/graphs/chat.py 注入研究上下文
  - [ ] 记忆不进入旧 checkpoint 持久正文
- [ ] 前端接续交互
  - [ ] "继续上次研究"按钮
  - [ ] 依据面板（记忆版本 + 资料引用）
  - [ ] 课题隔离验证

### 验收

- [ ] 不读取旧会话即可恢复目标和计划
- [ ] 课题 B 不召回课题 A
- [ ] 普通问答引用可打开
- [ ] 泛化"继续"提问能取得当前计划

---

## M3 模型抽取与记忆治理

### 任务

- [ ] 实现候选提取
  - [ ] 提取提示词设计
  - [ ] 结构化输出校验
  - [ ] 证据编号归属检查
  - [ ] POST /api/research/notebooks/{id}/memory-drafts (mode=extract)
- [ ] 实现 ETag 修订
  - [ ] PUT /api/research/notebooks/{id}/memories/{item_id}
  - [ ] 传递 If-Match
  - [ ] 版本冲突处理
- [ ] 实现遗忘
  - [ ] POST /api/research/notebooks/{id}/memories/{item_id}/forget
  - [ ] 调用 lifecycle forgotten
  - [ ] UI 明示历史仍可追溯
- [ ] 实现历史版本
  - [ ] GET /api/research/notebooks/{id}/memories/{item_id}/revisions
  - [ ] GET /api/research/notebooks/{id}/memories/{item_id}/revisions/{revision}
- [ ] 实现 uncertain 核对
  - [ ] 写入结果未知时进入 uncertain
  - [ ] 按 operation_id 核对
- [ ] 前端记忆治理
  - [ ] 候选面板（可编辑、逐条选中）
  - [ ] 记忆详情（版本、修订历史、来源引用）
  - [ ] 编辑和遗忘交互
  - [ ] 调用失败状态

### 验收

- [ ] 候选生成不写入已确认记忆
- [ ] 旧版本不能覆盖新版本
- [ ] 遗忘内容不再作为主动计划
- [ ] 伪造证据编号被拒绝

---

## M4 组会报告与完整页面

### 任务

- [ ] 实现报告生成服务（`open_notebook/research/report_service.py`）
  - [ ] 固定报告结构（6 部分）
  - [ ] 引用校验
  - [ ] 保存为 Note
  - [ ] Markdown 导出
- [ ] 实现报告 API
  - [ ] POST /api/research/notebooks/{id}/reports
  - [ ] GET /api/research/notebooks/{id}/reports/{id}/export
- [ ] 完善状态处理
  - [ ] loading / empty / unavailable / failed / uncertain
  - [ ] PowerContext 不可用时不生成声称包含最新进展的报告
- [ ] 前端完整页面
  - [ ] 组会报告预览
  - [ ] 依据查看
  - [ ] 保存为 Note
  - [ ] 导出 Markdown

### 验收

- [ ] 报告包含当前目标和真实引用
- [ ] 假设不改写为已验证成果
- [ ] 未提供实验时不捏造数值
- [ ] 来源失效正确标注

---

## M5 一键部署与基础验收

### 任务

- [ ] 构建修改版应用 Docker 镜像
- [ ] 编写 docker-compose.yaml（应用 + SurrealDB + PowerContext）
- [ ] 配置持久卷
- [ ] 编写健康探针
- [ ] 编写 seed_demo.py（样例数据导入）
- [ ] 编写 verify_acceptance.py（自动化验收）
- [ ] 编写 bootstrap.py（初始化配置）
- [ ] 清理配置中的真实凭据
- [ ] 编写 README.md（运行说明）

### 验收

- [ ] 干净环境安装启动
- [ ] 执行演示 12 步
- [ ] 重启后接续
- [ ] 中断 PowerContext 测试失败路径
- [ ] 重新运行种子脚本不破坏已生成绑定

---

## M6 Qoder Sites 与赛事材料

### 任务

- [ ] 创建 Qoder Sites 项目网站
- [ ] 编写网站内容（项目简介、架构、截图、运行说明）
- [ ] 发布公开版本
- [ ] 整理 Qoder 开发记录
- [ ] 整理每个阶段的 commit
- [ ] 核对最终提交信息

### 验收

- [ ] 未登录打开网站
- [ ] 所有链接有效
- [ ] 网站描述与实际功能一致
- [ ] 最终 commit 以比赛起点为祖先

---

## 当前进度

| 阶段 | 状态 | 完成度 |
|---|---|---|
| M0 | 🔄 进行中 | 60%（PowerContext 探针通过，原版运行待完成） |
| M1 | ⏳ 未开始 | 0% |
| M2 | ⏳ 未开始 | 0% |
| M3 | ⏳ 未开始 | 0% |
| M4 | ⏳ 未开始 | 0% |
| M5 | ⏳ 未开始 | 0% |
| M6 | ⏳ 未开始 | 0% |
