# 版本固定清单

版本：1.0  
更新日期：2026-10-27  
基准分支：`2026-competition-ecosystem`  
起点 commit：`d647275c` (chore: initialize 2026 competition ecosystem directories)

## 上游固定版本

| 项目 | 固定值 | 来源 | 备注 |
|---|---|---|---|
| PowerContext 源码 | commit `8ef4f645e66622e223cd49720d5f009f63ecff85` | tag `powercontext-v1.4.1` | 当前仓库比赛分支已包含 |
| PowerContext Python 包 | 1.4.1 | PyPI | `uv tool install "powercontext[cli,server]==1.4.1"` |
| Open Notebook 源码 | commit `a0f6f3081ae06328f0a451b3a3ef2959ca25721d` | GitHub `lfnovo/open-notebook` | 已导入 `qoder/app/` |
| Open Notebook pyproject 版本 | 1.15.0 | `qoder/app/pyproject.toml` | name="open-notebook" |
| Open Notebook Python | >=3.11,<3.13 | `qoder/app/pyproject.toml` | 推荐 3.12 |
| Open Notebook Node | 按 Dockerfile 与锁文件 | `qoder/app/.python-version` = 3.12 | M0 核对 |
| SurrealDB | 按上游 docker-compose.yml | `qoder/app/docker-compose.yml` | M0 核对镜像 tag |

## 运行环境

| 项目 | 实测值 |
|---|---|
| 操作系统 | Ubuntu 22.04 Linux x86_64 |
| Python（PowerContext 独立工具） | 3.12.16 (uv managed) |
| uv | 已安装 |
| PowerContext Server | 127.0.0.1:8001, role=all |
| PowerContext 存储 | SQLite (默认), 数据目录 `qoder/deploy/powercontext/data` |

## 版本变更记录

若因运行问题需要调整版本，在此记录原因、改后版本与重新验收结果。

（当前无调整）
