# Technical Context

- **语言**: Python 3.12+
- **后端**: FastAPI
- **前端**: HTML + HTMX (拒绝 React 等前端框架)
- **数据库**: SQLite
- **AI 接口**:
- **开发环境**: VS Code + Cline

## 操作系统与 Shell

- **系统**: Windows 10
- **PowerShell 版本**: 5.x （位于 `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe`）
  - ⚠️ **不支持 `&&`（逻辑与）和 `||`（逻辑或）操作符**
  - 多条命令用 `;` 分隔，或显式使用 `if ($?) { ... } else { ... }`
  - 若要使用 `&&`/`||`，需在 **cmd** 中执行，或在 PowerShell 中直接写单条命令

## Python 环境

- **虚拟环境路径**: `.\venv\`
- **Python 解释器**: `.\venv\Scripts\python.exe`
  - **重要**: 所有命令都必须用 venv 的 Python，系统 Python 缺少 `readmdict` 等依赖包
  - 系统 Python 路径: `C:\Users\user\AppData\Local\Programs\Python\Python310`
- **依赖包 `readmdict`**: 安装在 `.\venv\Lib\site-packages\readmdict\`
  - 从 `mdict_utils.base.readmdict` 改为了 `readmdict`（`pip install readmdict` 安装）

## 常用命令

- **启动服务器**: `cd web2mdd && venv\Scripts\python -m app.main`
  - 实际执行: `.\venv\Scripts\python.exe -m app.main`
- **运行测试**: `.\venv\Scripts\python.exe -m app.test_dict`
- **安装包**: `.\venv\Scripts\python.exe -m pip install <包名>`
