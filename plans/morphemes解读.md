# morphemes.json 解读文档

> 最后更新：2026-06-21
> 状态：初步解读，可能随着使用深入而修正

## 1. 文件概览

- **路径**: `数据资料/morphemes.json`
- **大小**: 约 1MB
- **词条数**: 2435 个
- **内容**: 英文单词的词素（morpheme）集合，包括前缀、后缀和词根

## 2. 数据结构

每个词条的键名是一个词素的标识符，值是一个对象，结构如下：

```json
{
  "词素标识符": {
    "forms": [
      {
        "root": "实际用于匹配的字符串",
        "form": "去符号后的形式",
        "loc": "prefix | suffix | embedded",
        ...其他可选字段
      }
    ],
    "meaning": ["含义1", "含义2"],
    "origin": "词源（如 Latin, Greek）",
    "etymology": "详细词源说明",
    "examples": ["示例单词1", "示例单词2"]
  }
}
```

### 关键字段说明

| 字段 | 说明 |
|------|------|
| `forms` | 一个词素可能有多种书写形式（变体），每种形式是一个独立的可匹配单元 |
| `forms[].root` | **实际用于匹配的字符串**，这是最重要的字段 |
| `forms[].form` | 去连字符后的形式，用于显示 |
| `forms[].loc` | 位置：`prefix`(前缀)、`suffix`(后缀)、`embedded`(嵌入的词根) |
| `meaning` | 词素含义列表 |
| `examples` | 仅供参考的示例单词，不参与匹配逻辑 |

## 3. 三种 loc 类型

### 3.1 prefix（前缀）

放在单词**开头**的语素。

**命名规则**: 通常不带连字符，或带尾随连字符
- `pre-` → root: `"pre-"` → 匹配 `"pre"`
- `Afro` → root: `"Afro-"` → 匹配 `"Afro"`
- `Hell-` → root: `"Hell-"` → 匹配 `"Hell"`

**示例**:
```
"pre-": {
  "forms": [{"root": "pre-", "form": "pre", "loc": "prefix", ...}],
  "meaning": ["before"]
}

"ap-, apo-": {
  "forms": [
    {"root": "apo-", "form": "apo", "loc": "prefix"},
    {"root": "ap-", "form": "ap", "loc": "prefix"}
  ],
  "meaning": ["away from", "separate"]
}
```

### 3.2 suffix（后缀）

放在单词**结尾**的语素。

**命名规则**: 通常带前导连字符
- `-able` → root: `"-able"` → 匹配 `"able"`
- `-al` → root: `"-al"` → 匹配 `"al"`
- `-ation` → root: `"-ation"` → 匹配 `"ation"`

**示例**:
```
"-able": {
  "forms": [{"root": "-able", "form": "able", "loc": "suffix", ...}],
  "meaning": ["able to", "capable of"]
}

"-ary": {
  "forms": [{"root": "-ary", "form": "ary", "loc": "suffix", ...}],
  "meaning": ["relating to", "quality", "place where"]
}
```

### 3.3 embedded（嵌入的词根）

放在单词**中间**的语素，通常是词根。

**命名规则**: 通常带前后连字符
- `-log-` → root: `"-log-"` → 匹配 `"log"`
- `-plic-` → root: `"-plic-"` → 匹配 `"plic"`
- `abil` → root: `"-abil-"` → 匹配 `"abil"`

**示例**:
```
"-log-": {
  "forms": [{"loc": "embedded", "root": "-log-", "form": "log"}],
  "meaning": ["word", "reason", "speech"]
}

"plic-": {
  "forms": [
    {"root": "plic-", "form": "plic", "loc": "prefix"},
    {"loc": "embedded", "root": "-plic-", "form": "plic"}
  ],
  "meaning": ["bend", "fold", "tangle"]
}
```

## 4. 匹配用的 root 字符串提取规则

从 `forms` 数组中提取用于匹配的字符串：

1. 取 `root` 字段
2. **去掉首尾的连字符 `-`**
3. 得到的字符串就是要在单词中匹配的内容

| root 字段 | 匹配字符串 | 类型 |
|-----------|-----------|------|
| `"pre-"` | `"pre"` | 前缀 |
| `"-able"` | `"able"` | 后缀 |
| `"-log-"` | `"log"` | 词根 |
| `"ap-"` | `"ap"` | 前缀 |
| `"-ation"` | `"ation"` | 后缀 |

## 5. 单词拆分算法

### 5.1 基本流程

对于输入单词（如 `preliminary`）：

```
步骤1: 匹配前缀（从 forms 中提取所有 loc=="prefix" 的 root）
       preliminary → 匹配到 "pre" → 结果: "pre."
       
步骤2: 匹配后缀（从剩余部分末尾匹配）
       liminary → 匹配到 "-ary" → 结果: "pre.inary"
       
步骤3: 匹配词根（在剩余部分中查找 embedded）
       limin → 在 embedded 中查找 → 可能找不到
       
最终结果: "pre.limin.ary" 或 "pre.linary"
```

### 5.2 关键原则

1. **最长匹配优先**: 对于同一位置，优先匹配较长的字符串
   - 如 `biology`，`-ology` 和 `-logy` 都是后缀，优先匹配更长的
   
2. **按位置顺序**: 前缀（开头）→ 词根（中间）→ 后缀（结尾）

3. **容错处理**: 如果某个部分找不到匹配，保留原样

### 5.3 示例演示

| 单词 | 前缀 | 词根 | 后缀 | 结果 |
|------|------|------|------|------|
| `application` | `ap-` | `plic-` | `-ation` | `ap.plic.ation` |
| `preliminary` | `pre-` | (无) | `-ary` | `pre.limin.ary` |
| `biology` | (无) | (无) | `-logy` | `bio.logy` |
| `cat` | (无) | (无) | (无) | `cat` |
| `acceptable` | (无) | (无) | `-able` | `accept.able` |

## 6. 数据统计

| 类型 | 数量 |
|------|------|
| 总词条数 | 2435 |
| 前缀 (prefix) | ~3034 个 forms |
| 后缀 (suffix) | ~850 个 forms |
| 词根 (embedded) | ~1026 个 forms |

## 7. 已知问题和待改进

1. **词根覆盖不全**: 很多单词的词根在数据库中不存在，如 `limin`
2. **合并词条**: 有些词条合并了多个相关词素（如 `ac-, acm-, acr-`），需要仔细解析
3. **大小写问题**: 部分前缀首字母大写（如 `Afro`），部分小写，匹配时需统一转小写
4. **变体形式**: 同一个词根可能有多个变体（如 `loga-`, `logi-`, `logo-`），需要全部列出
5. **重叠问题**: 某些字符串可能同时出现在 prefix 和 suffix 中，需要区分上下文

## 8. 策略对比测试结果 (2026-06-21)

### 测试单词及结果

| 单词 | 策略A (词根优先) | 策略B (后缀优先) | 获胜方 |
|------|-----------------|-----------------|--------|
| application | ap.plic.ation (4.0) | ap.plic.ation (4.0) | 平局 ✓ |
| preliminary | pre.li.min.ary (3.8) | pre.li.min.ary (3.8) | 平局 |
| biology | bio.logy (3.0) | bi.ology (2.0) | A |
| cat | cat (-0.3) | cat (1.0) | B (但cat不应是前缀) |
| previously | previously (-1.0) | pre.vious.ly (1.5) | B |
| impossible | im.poss.ible (4.0) | im.poss.ible (4.0) | 平局 ✓ |
| acceptable | ac.cept.able (4.0) | ac.cept.able (4.0) | 平局 ✓ |
| education | e.duc.ation (2.9) | duc.e.ation (2.9) | 平局 |
| dialogue | dia.ue.log (2.8) | dia.logue (2.0) | A (但结果不对) |
| complicated | com.plic.ated (4.0) | com.plic.ated (4.0) | 平局 ✓ |

### 发现的问题

1. **短前缀误匹配**: `cat-`, `bi-`, `im-` 等2字符前缀容易误匹配
2. **词根vs后缀混淆**: `log` 可能被识别为词根而非 `logue` 后缀
3. **bio- 被误识别为词根**: 策略A中 `bio` 被 `_find_root` 匹配了

### 改进方向

1. 前缀需要设置最小长度（至少2-3字符）
2. 当同一个字符串同时出现在 prefix 和 embedded 中时，需要根据位置判断
3. 后缀匹配应该优先于词根匹配（因为后缀在末尾，位置确定）
4. 评分机制需要调整，避免短词干被错误拆分

## 8. 与其他文件的关系

项目中还有其他相关文件：
- `_prefixes.txt` — 前缀列表
- `_suffixes.txt` — 后缀列表
- `常见字母组合.json` — 字母组合数据
- `常见元音.json` / `常见辅音.json` — 音素数据

这些文件可能与 morphemes.json 配合使用，实现更完整的单词拆分功能。