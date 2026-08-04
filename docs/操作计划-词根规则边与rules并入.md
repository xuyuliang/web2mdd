# 操作计划：词根吃拼写规则边 + 并入 rules_clean

日期：2026-08-04。状态：**待实施**。

> 注：struct/struc/stitut 只是讨论时用的**示意例子**，不是测试用例，不进入验收清单。

## 1. 背景与目标

管线三步脚本：`build_segment_freqs.py` → `build_allomorph_groups.py` → `build_confirmed_affixes.py`（详见 `实施计划.md`、`docs\切分算法.md`）。

当前数字：segment-freqs 3210 段；groups nodes=19312 / edges_merged=8144 / groups=11805 / review=11789；anki_highfreq 2715 条目。

### 历史口径变更（重要，勿搞混）

- **确认门 `MIN_COUNT`：原来 `3`（身份合并数 ≥3 才放行整组、才能写入输出），现改为 `1`** —— 即"出现 1 次也写入 anki_highfreq.json"，不再是 3 次才写（改于 2026-08-04，见 `scripts/build_confirmed_affixes.py:18`）。
- **对输出文件的具体影响（实测当前 2715 条）**：`次数=0` 918 条、`=1` 1113 条、`=2` 305 条、`≥3` 379 条；最小 `次数=0`。例如条目 `sor`（`type=""`、`次数=2`、`merged_count=2`，anki_highfreq.json 约 9780-9791 行）此前不会写入，现因 MIN_COUNT=1 写入。
- 文件 45795 行 ≠ 条目数：`json.dump(indent=2)` 每条约 17 行，2715 条 × 16.9 ≈ 45795 行；文件按 `-次数` 排序，次数≥3 的 379 条占前 ~6400 行，次数=2 区段约 6400~11500 行（`sor` 所在）。
- 语义不变：`次数` = 每个表面形在语料对应位置的真实出现次数（不虚高，可为 0）；`merged_count` = 所属身份的合并总次数（`MIN_COUNT` 的依据字段）。
- 注意：`次数=0` 的条目仍会存在（roots 声明的变体，如 tenax 类），它们凭"roots 身份 + 组内合并"进入，不代表语料中出现过。

### 本次要做的三件事

- **A. 并入 `蒸馏计划2完整词根/output/rules_clean.jsonl`**（23695 词切分）到次数统计，作为第二语料源。
- **B. 把 `rule_edges_for` 改为候选索引式生成**（等价重构，否则 root 位置全两两会 4500 万对爆炸）。
- **C. 让 root 位置也吃拼写规则边**（pad/elide/assimilation），与 prefix/suffix 走同一套门。

## 2. 改动 A：并入 rules_clean（`scripts/build_segment_freqs.py`）

口径（已拍板，勿改）：
1. **并入同一次数**：两源计进同一 segment-freqs.json，`count`=合计。
2. **共存词 anki 优先**：同词在两源（2786 个）只取 anki_splits 切分；rules 只补 anki 没有的词。
3. **单段整词不计段**：rules 中 `len(segments)==1` 的词跳过（3874 个）；anki 侧原 747 个单段词维持原样照计。
4. 段定位：下标 0→first、末→last、余→middle；每词每段去重计 1 次；段 `.lower()`。

实现：保留现有 anki 逻辑不动；新增 rules 源，只处理不在 anki 词集的词、跳过单段，按口径 4 累加。输出格式/路径不变。下游门槛零改动。

## 3. 改动 B：`rule_edges_for` 候选索引式（等价重构）

文件 `scripts/build_allomorph_groups.py:253-285`。

- **pad/elide**：对每个长形 `longer`(L+1) 逐 i 删一字符 `cand=longer[:i]+longer[i+1:]`，查长度 L 的形集合命中即得对；`i` 即插入位，`longer[i]` 即插字符，据此判 `elide`（`ins_pos>0 and longer[ins_pos-1]==ins_ch`）或 `pad`。
- **assimilation**：同长桶内，对每个形只试边界位 `k in (0,L-1)` × 辅音 `"bcdfghjklmnpqrstvwxz"`，查桶集合命中且非自身。
- 结果去重语义同旧。
- **必须先回归**：只改 B、保持 `for p in ("prefix","suffix")`，对比新旧 `edges_merged`/`review` **完全一致**，不一致先修再继续。

实测 root 候选量级：pad≈12.6k、assim≈11.9k，可控。

### 词根"只在右侧变形"的词形规则（用户指定，勿越界）

对**词根（root/中间位置）**：所有变形只在**右侧**发生，不做左侧试探。例：`graph` 只会变 `graphy`（右加 y），不会变 `pgraph`（左加 p）。

落地到候选生成（`rule_edges_for` 需按 `pos` 区分探测边界）：
- **pad/elide（root）**：只做**右端插入/删除**——即 `longer == shorter + 尾字符`（`cand = longer[:-1]` 删末位查短形集合），不做左侧/中间插删。
- **assimilation（root）**：只在**右边界 `L-1`** 替换辅音，不试左边界 `0`。
- **prefix/suffix 保持现状**（两侧/任意插入位都试，靠释义门过滤），以保证改动 B 等价性回归不受影响。

## 4. 改动 C：root 位置跑规则边

文件 `scripts/build_allomorph_groups.py` main()（:368 `for p in ("prefix", "suffix"):`）→ 加 `"root"`。门 2 释义门 / 门 3 rank 过滤 / review 全部原样。**root 的候选生成只探右侧变形**（见 §3 词形规则）。

预期：review 扩容（root 候选 gate，数千～上万条）；可能出现新 root 合并。两端无释义的 root 对由 `decide_merge` 秒拒且 min rank>1 丢弃，不写 review。

## 5. 实施顺序

1. 备份四个输出：`segment-freqs.json`、`allomorph_groups.json`、`allomorph_review.json`、`anki_highfreq.json`（git 或复制）。
2. **改动 A** → 重跑 `build_segment_freqs.py`，验 §6.1。
3. **改动 B** → 重跑 `build_allomorph_groups.py` 做等价回归（§6.2 第 1 项）通过后才动 C。
4. **改动 C** → 重跑，验 §6.2。
5. 重跑 `build_confirmed_affixes.py`，验 §6.3。
6. 更新 `实施计划.md`、`docs\切分算法.md`。

## 6. 验证清单（不含 struct 例子）

### 6.1 改动 A 后
- 脚本正常跑完，打印 "Segments total" 明显变大。
- 抽查若干段的 `count` 较旧值上升（新增语料证据生效）。
- 抽查共存词（同时出现在两源的词）：其段计数只按 anki 切分，未被 rules 重复计。

### 6.2 改动 B/C 后
- **B 回归**：prefix/suffix 的 `edges_merged`、`review` 与旧输出**完全一致**。
- 脚本正常跑完，耗时在可接受范围（记录时间）。
- review 全量仍每条带 `examples` 与 `positive` 字段。
- root 位置确实新增了候选（review 里 root 位置条目数 > 0）。
- 抽查若干大族（per/par/cur/the/ten）无异常合并；可疑项应被门拦进 review。

### 6.3 build_confirmed_affixes 后
- 正常输出，`次数`=真实位置频次、`merged_count`=身份合计语义不变。
- 原先 次数=0 的 roots 变体（如 tenax 类）仍在。
- 新增语料导致的计数上涨合理，无 NaN/缺字段。

## 7. 风险与注意

- B 的等价性是最大翻车点：必须独立回归，别与 A/C 混排。
- review 扩容若失控，再议"root 候选仅限 roots 参与的对"；当前预计 min rank>1 过滤已兜住大部分。
- 门 2/3/4 一律不动。

## 8. 关键文件/行号速查

- `build_segment_freqs.py`：全文改造（加第二源）。
- `build_allomorph_groups.py`：`RULES_PATH`(:31)；`rule_edges_for`(:253-285)；main 循环(:368)；`decide_merge`(:304-333) 与 `add_review`(:343-360) 不动。
- `build_confirmed_affixes.py`：`MIN_COUNT=1`(:18)、确认门(:65)、真实次数(:74-78)，均不动。

## 9. 待确认问题

- 无。口径与顺序已定，明天按 §5 执行。
