# Active Context

- **当前任务**: 解决 python-lzo 无法安装的问题，改用 mdict-utils 实现纯 Python LZO 解压
- **最近修改**:
  - 将 `readmdict` 和 `lzo` 依赖替换为 `mdict-utils`（已在 venv 中安装）
  - `main.py`: `from readmdict import MDX, MDD` → `from mdict_utils.base.readmdict import MDX, MDD`，`import lzo` → `from mdict_utils.base import lzo`
  - `test_dict.py`: 同样替换为 `mdict_utils` 的导入
  - `_decompress_block` 中的 LZO 解压调用改为纯 Python 版本：`lzo.decompress(b'\xf0' + ...)` → `lzo.decompress(data[8:], initSize=decomp, blockSize=1308672)`
  - `mdict-utils` 自带的纯 Python LZO 实现位于 `mdict_utils/base/lzo.py`，无需 C 编译
- **启动方式**: `cd web2mdd && venv\Scripts\python -m app.main`
- **下一步计划**: 在"查字典"的返回数据中 把词频信息单独抽出来，不需要在web页面上显示它，只需要做成api接口就可以了。
