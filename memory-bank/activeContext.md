# Active Context

- **当前任务**: 移除 MDD 多媒体依赖（用户删除了 TLD.mdd，代码已清理干净）
- **最近修改**:
  - `main.py`: 移除了 `MDD` 导入（`from mdict_utils.base.readmdict import MDX, MDD` → `from mdict_utils.base.readmdict import MDX`）
  - `main.py`: 删除了 `MDD_PATH` 常量定义
  - `main.py`: 删除了整个 `MDDReader` 类
  - `main.py`: 删除了 `mdd_reader` 的初始化和条件加载
  - `main.py`: 删除了 `/api/media/{path:path}` 路由
  - `main.py`: 清理了未使用的 `Response` 导入（改为从 `fastapi.responses` 仅保留 `HTMLResponse, FileResponse`）
  - `templates/index.html`: 删除了前端 `fixMediaPaths` 的 JavaScript 代码（包括 htmx:afterSwap 监听器）
- **启动方式**: `cd web2mdd && venv\Scripts\python -m app.main`
- **下一步计划**: 在"查字典"的返回数据中 把词频信息单独抽出来，不需要在web页面上显示它，只需要做成api接口就可以了。
