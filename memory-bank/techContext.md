# Technical Context

- **语言**: Python 3.12+
- **后端**: FastAPI
- **模板引擎**: Jinja2 3.1.6（通过 `Jinja2Templates` 集成）
- **前端**: HTML + HTMX（拒绝 React 等前端框架）
- **词典数据格式**: MDX (MDict 格式)，通过 `readmdict` 库读取
- **数据存储**: 无独立数据库，词典数据直接来自 TLD.mdx 文件；索引缓存使用 pickle 序列化文件（.pkl）
- **词根词缀数据**: 纯文本文件 `_prefixes.txt`（149个前缀）和 `_suffixes.txt`（198个后缀）
- **开发环境**: VS Code + Cline
- **VS Code 工作区配置**: `.vscode/settings.json` - 设置 `PYTHONIOENCODING=utf-8` 解决中文/Unicode 终端乱码
- **VS Code 调试配置**: `.vscode/launch.json` - 预置 FastAPI 服务器、Anki 数据探查等调试任务
- **系统代码页**: 936 (GBK)，通过 `terminal.integrated.env.windows.PYTHONIOENCODING` 覆盖为 UTF-8

## Python 环境

- **虚拟环境路径**: `.\venv\`
- **Python 解释器**: `.\venv\Scripts\python.exe`
- **依赖包 `readmdict`**: 安装在 `.\venv\Lib\site-packages\readmdict\`
  - 从 `mdict_utils.base.readmdict` 改为了 `readmdict`（`pip install readmdict` 安装）

## 目录结构

```
查词拆词/
├── app/                          # 主程序包
│   ├── __init__.py               # 包初始化
│   ├── main.py                   # FastAPI 应用入口，MDXReader 词典读取
│   ├── affix_loader.py           # 词根词缀分析模块
│   └── test_dict.py              # 词典读取测试脚本
├── .vscode/                      # VS Code 工作区配置
│   ├── settings.json             # 编码/环境配置（PYTHONIOENCODING=utf-8）
│   └── launch.json               # 调试配置（4个预置任务）
├── templates/                    # Jinja2 模板
│   ├── index.html                # 首页
│   └── partials/                 # HTMX 片段模板
├── static/
│   └── style.css                 # 页面布局样式
├── memory-bank/                  # 项目档案
├── plains/                       # 方案分析文档
├── _prefixes.txt                 # 前缀列表（149个）
├── _suffixes.txt                 # 后缀列表（198个）
├── .clinerules                   # Cline 规则
├── .gitignore
├── 使用方法.txt                  # 人类使用说明
└── 前缀后缀.xlsx                 # 前缀后缀源数据
```

## 常用命令

- **启动服务器**: `.\venv\Scripts\python.exe -m app.main`
- **运行测试**: `.\venv\Scripts\python.exe -m app.test_dict`
- **安装包**: `.\venv\Scripts\python.exe -m pip install <包名>`
- **VS Code 调试**: 按 F5 选择预置配置（FastAPI 服务器 / Anki 数据探查 / 数据清洗 / 词根词缀测试）

## 词典数据

- **词典文件**: `The little dict/TLD.mdx`（被 .gitignore / .clineignore 排除）
- **词典 CSS**: `The little dict/p.css`
- **索引缓存**: `TLD.mdx.pkl`（自动生成，加速启动）
- **词条数**: 约 436 万条
