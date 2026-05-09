# Active Context

- **当前任务**: 单独获取词频的值（已完成）
- **最近修改**:
  - `main.py`: 在 `MDXReader` 类中新增 `get_rank(word)` 方法，从 HTML 解析 `<span class="rank">\d+</span>` 提取第一个 rank 值
  - `main.py`: 新增 `/api/rank` API 接口，接受 `?word=` 参数，返回 JSON `{"word": ..., "rank": ..., "found": ...}`
  - `test_dict.py`: 新增测试3（get_rank 词频提取），包含已知词频验证、不存在词、空字符串、大小写测试
- **API 接口**: `/api/rank?word=splice` -> `{"word": "splice", "rank": 20290, "found": true}`
- **启动方式**: `venv\Scripts\python -m app.main`
- **下一步计划**: 第2项 - 支持简单的正则表达式查字典
