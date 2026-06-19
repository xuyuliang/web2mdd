# Active Context

- **当前任务**: 实现词根词缀分析与同源词查找（部分完成：词根词缀切分已完成；同源词查找待实现）
- **最近修改**:
  - `app/main.py`:
    - 引入 `AffixLoader`，在 `/api/lookup` 精确匹配时自动对单词进行词根词缀分析
    - 调用 `affix_loader.analyze(word, is_valid_word=is_valid_word)` 进行切分
    - 查询词干的词典释义，通过 Jinja2 渲染 `_affix_result.html` 附加到查词结果后
    - 新增 `is_valid_word()` 函数，用于验证词干是否为有效单词
  - `app/affix_loader.py`：新增词根词缀分析模块
    - `AffixLoader` 类从 `_prefixes.txt`（149个前缀）和 `_suffixes.txt`（198个后缀）加载数据
    - 按长度降序排列，优先匹配更长的词缀
    - `analyze()` 方法支持 `is_valid_word` 回调函数验证词干有效性
    - 包含内置测试用例
  - `templates/partials/_affix_result.html`：新增词根词缀分析结果片段模板
    - 显示单词拆分（前缀-词干-后缀，不同颜色高亮）
    - 详细展示前缀/后缀/词干信息
    - 可折叠展开词干的词典释义
  - `_prefixes.txt`、`_suffixes.txt`：新增前缀/后缀数据文件
  - 引入 Jinja2 模板引擎，替换手动拼接 HTML（已完成）
  - `inspect_anki_data.py`：新增 Anki 数据质量探查脚本（已完成）
  - `.vscode/settings.json`：新增 VS Code 编码环境配置，设置 `PYTHONIOENCODING=utf-8` 解决终端中文/Unicode 乱码
  - `.vscode/launch.json`：新增 4 个 Python 调试配置（FastAPI 服务器 / Anki 数据探查 / 数据清洗 / 词根词缀测试），均预设 UTF-8 编码
  - 清理：删除项目根目录遗留的 `$null` 文件（命令错误产物）和 `_debug_output.txt`（临时调试输出）
- **API 接口**:
  - `/api/lookup?word=xxx`：精确匹配时返回词典内容 + 词根词缀分析结果（附加在内容后）

- **启动方式**: `venv\Scripts\python -m app.main` 或 VS Code F5 调试启动
- **数据探查工具**: `.\venv\Scripts\python.exe inspect_anki_data.py` 或 VS Code 调试配置
- **下一步计划**: 
  1. 第2项 - 支持简单的正则表达式查字典（待实现）
  2. 第3项 - 词根词缀切分 见"切分规划.md" (待实现)
  3. 第4项 - 拼写相似单词查找 见"切分规划.md"（待实现）
  4. 种子数据清洗 - 已从 myankidata.anki2 中提取 202 条有效切分数据到 plains/anki-valid-data.csv
