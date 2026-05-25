# AGENTS.md

## 项目背景

这是一个 Telegram 克隆/分发系统。

当前架构：
- Telethon 用户号负责监听、采集、下载源频道内容。
- 官方 Telegram Bot API 负责分发到目标频道。
- 后端目录是 `backend/`。
- 前端管理端目录是 `admin/`。

## 工作方式


标准流程：
1. 先阅读相关文件和调用链。
2. 先说明根因、涉及文件、修改方案。
3. 允许直接修改代码。
4. 允许做大规模重构。
5. 允许修改数据库结构。
6. 允许新增数据库迁移脚本。
7. 允许修改前端、后端、数据库、配置文件。
8. 涉及数据库结构变更时，必须先备份数据库文件。
9. 涉及删除数据、清空表、删除账号、删除 session、删除 token、删除 logs/data/accounts 时，必须先询问用户。
10. 不允许自动 git commit。
11. 不允许自动 git push。
13. 如果修改 `requirements.txt` 或 `package.json`，必须说明新增依赖原因。
14. 所有回复使用中文。

## 后端规则

后端运行目录：
- `D:\MyProject\telegram-bot\backend`

虚拟环境：
- 项目根目录 `.venv`

常用命令：

```powershell
cd D:\MyProject\telegram-bot\backend
..\.venv\Scripts\Activate.ps1
python run.py
```
