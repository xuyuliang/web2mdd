# Active Context

- **当前任务**: 引入 Jinja2 模板引擎，替换手动拼接 HTML（已完成）
- **最近修改**:
  - `main.py`:
    - 引入 `Jinja2Templates`，添加 `templates = Jinja2Templates(directory=TEMPLATES_DIR)`
    - 移除 `_load_index_html()` 函数和 `HOME_HTML` 全局变量
    - 移除 `HTMLResponse` 导入（不再使用）
    - `/` 首页：改为 `templates.TemplateResponse("index.html", ...)`，注入 `request`
    - `/api/lookup`：改为渲染 `partials/_lookup_result.html` 或 `partials/_suggestions.html` 片段模板
  - `templates/index.html`：内容不变，但转为由 Jinja2 渲染（无变量注入）
  - 新建 `templates/partials/` 目录：
    - `_lookup_result.html`：`<div class="dict-content">{{ content | safe }}</div>`
    - `_suggestions.html`：拼写建议片段，含 Jinja2 的 `{% if %}` / `{% for %}` 模板语法
  - 新增依赖：`jinja2==3.1.6`
- **API 接口**: 无变更 `/api/lookup` 返回内容不变，`/api/rank` 不变
- **启动方式**: `venv\Scripts\python -m app.main`
- **下一步计划**: 第2项 - 支持简单的正则表达式查字典
