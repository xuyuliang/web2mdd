# Progress

- [x] 完成了查字典功能（MDXReader 词典读取、精确匹配、前缀匹配）
- [x] 1. 单独获取到词频的值（`/api/rank` 接口，正则提取 RANK 最小值）
- [x] 引入 Jinja2 模板引擎，重构后端 HTML 渲染
- [x] 3a. 词根词缀切分（`AffixLoader` 类 + `_affix_result.html` 模板）
  - 从 `_prefixes.txt` 和 `_suffixes.txt` 加载前缀/后缀数据
  - 按长度降序匹配，优先匹配更长的词缀
  - 词干有效性验证（防止误切）
  - 单字符后缀保护（防止 hello 被切 -o）
  - 查询词干的词典释义
- [x] Anki 数据质量探查（`inspect_anki_data.py`）
  - 探查 `myankidata.anki2` 数据库结构
  - 自洽性校验：第6项第一个切分词去点后 == 第0项
  - 输出质量报告 `plains/anki-data-quality-report.md`
  - 提取 202 条有效切分数据到 `plains/anki-valid-data.csv`
- [ ] 2. 支持简单的正则表达式查字典
- [ ] 3b. 同源词查找（基于词根词缀分析结果，查找共享词干的单词）
- [ ] 4. 能根据拼写，查找拼写相似的单词
