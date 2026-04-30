# System Patterns

- **API 风格**: 异步优先 (async/await)
- **数据流**: 前端通过 HTMX 请求后端 API，后端返回 HTML 片段。
- **目录结构**:
  - /app (主程序 — main.py, test_dict.py, **init**.py)
  - /static (样式 — style.css)
  - /templates (HTML 模板 — index.html)
  - /memory-bank (项目档案)
  - 根目录保持: .clineignore.md, .gitignore, 使用方法.txt
  - 词典数据 (The little dict/) 通过 .gitignore / .clineignore 排除
