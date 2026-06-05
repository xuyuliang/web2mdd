# Anki 数据质量报告
生成时间: 2026-06-05 04:55:55

## 1. Schema 概览

- 数据库表: cards, col, config, deck_config, decks, fields, graves, notes, notetypes, revlog, sqlite_stat1, sqlite_stat4, tags, templates
- 字段分隔符: \x1f (Unit Separator)
- 字段索引 0 = 单词, 6 = 切分数据（点号分隔）
- Note Model: **(empty)**
  - 字段定义: (空)

### 各表行数

| 表名 | 行数 |
|------|------|
| cards | 8,269 |
| col | 1 |
| config | 46 |
| deck_config | 2 |
| decks | 12 |
| fields | 38 |
| graves | 0 |
| notes | 4,135 |
| notetypes | 10 |
| revlog | 475,084 |
| sqlite_stat1 | 21 |
| sqlite_stat4 | 281 |
| tags | 2 |
| templates | 14 |

## 2. 基础统计

| 指标 | 数值 |
|------|------|
| 笔记总数 | 4,135 |
| 唯一单词数（大小写敏感） | 4,135 |
| 唯一单词数（大小写不敏感） | 4,135 |
| 有标签条目 | 1,791 |
| 无标签条目 | 2,344 |
| 数据时间跨度 | 2025-02-10 ~ 2026-06-05 |

### 字段填充率

| 字段索引 | 填充数 | 填充率 | 空值数 |
|---------|--------|--------|--------|
| 0 | 4,135 | 100.0% | 0 |
| 1 | 4,121 | 99.7% | 14 |
| 2 | 4,134 | 100.0% | 1 |
| 3 | 3,612 | 87.4% | 523 |
| 4 | 3,655 | 88.4% | 480 |
| 5 | 3,999 | 96.7% | 136 |
| 6 | 4,021 | 97.2% | 114 |
| 7 | 49 | 1.2% | 4,086 |

## 3. 自洽性校验结果

**判定标准**：第 6 项开头的第一个切分词去掉点号后，应与第 0 项（单词）一致。

| 结果 | 数量 | 占比 |
|------|------|------|
| [OK] **有效**（去点后匹配） | 1,680 | 40.6% |
| [!!] 第6项无点号切分词 | 1,568 | 37.9% |
| [!!] 去点后不与第0项匹配 | 364 | 8.8% |
| [!!] 第6项为空 | 523 | 12.6% |

### 无效数据示例（前10条）

| note_id | 第0项（单词） | 第6项（前60字符） | 失败原因 |
|---------|-------------|-----------------|---------|
| 1494899176086 | tyrant | autocrat 只强调独裁，没说残暴 | field6_no_dot_word |
| 1567497480175 | authoritarian | author作家i.tar.ian<br>authority <br>honorarium （给专业人士的）酬金 | field6_mismatch |
| 1567497480176 | coinage |  | field6_empty |
| 1567497480177 | flex | 联想：花线是软的，相对硬线可以屈伸<br>&nbsp;&nbsp; flex<br>re.flex 本能反应 | field6_mismatch |
| 1567497480178 | extradition | ex+tradition 传统：送中不是传统 | field6_no_dot_word |
| 1567497480180 | propaganda | 好多a<br>propagate v.宣传。增殖 | field6_no_dot_word |
| 1567497480182 | ardent | ardour 激情 热情<br>arduous 艰难的（需要大量努力的）（尤其是需要长时间的） | field6_no_dot_word |
| 1567497480185 | concoct |  | field6_empty |
| 1567497480187 | praise | appraise [&nbsp;əˈpreɪz] v.估价<br>appraisal [&nbsp;əˈpreɪzl]  | field6_no_dot_word |
| 1567497480189 | warfare |  | field6_empty |

## 4. 重复分析

- GUID 重复组数: 0（共 0 条重复条目）
- 单词级重复（大小写敏感）: 0 组（共 0 条）
- 单词级重复（大小写不敏感）: 0 组（共 0 条）

## 5. 相关词统计（仅限有效数据）

| 指标 | 数值 |
|------|------|
| 所有相关词总数 | 3,993 |
| 唯一相关词数 | 3,204 |
| 平均每条有效数据的相关词数 | 2.38 |

### Top-20 高频相关词

| 相关词 | 出现次数 | 来源主词示例 |
|--------|---------|-------------|
| v.n | 29 | appealing, blunder, burly, census, conceal |
| n.v | 29 | annotate, appellant, assent, assimilate, charade |
| re.pose | 6 | depose, impose, propose, repose, repository |
| thren.ody | 6 | parody, pastiche, rhapsody, threnody |
| im.pose | 5 | depose, impose, impostor, propose, repose |
| de.pose | 5 | depose, deposition, impose, propose, repose |
| dis.pose | 5 | depose, dispense, impose, propose, repose |
| vt.vi | 5 | bumble, crumple, dwindle, respire, tussle |
| pre.mise | 5 | compromise, premise, premises, pretext, surmise |
| pre.rog.ative | 5 | abrogate, derogatory, perquisite, prerogative, surrogate |
| pro.pose | 4 | depose, impose, propose, repose |
| im.pre.cation | 4 | implication, imprecation, predicament, prevaricate |
| arab.esque | 4 | brusque, burlesque, grotesque, picturesque |
| grot.esque | 4 | brusque, burlesque, grotesque, picturesque |
| in.flict | 4 | afflict, inflect, inflict, profligate |
| al.lege | 4 | allegation, allege, allegory, allegro |
| al.leg.ory | 4 | allegation, allege, allegory, allegro |
| pro.mise | 4 | compromise, premise, promising, surmise |
| bou.quet | 4 | banquet, boutique, parquet, sobriquet |
| dys.phor.ia | 4 | anhedonia, aphasia, aphorism, dysphoria |

## 6. 字符问题

- 含不可见字符条目: 1
  - 示例 ID: 1573384045715
- 含首尾空格条目: 87
  - 示例 ID: 1567497480197, 1567522924865, 1567522924869, 1567522924875, 1567731342745, 1567731342773, 1568109940840, 1568186433360, 1568186433375, 1568644985137
- 中文混入单词字段: 0

## 7. 总结与建议

- **有效数据比例**: 40.6%（1680 / 4135）
- **整体质量评价**: (bad) 较差

### 建议优先处理

- 第6项为空（523 条）：这些条目完全没有切分数据，建议直接删除
- 第6项无点号切分词（1568 条）：切分数据格式异常，需人工审查
- 去点后不匹配（364 条）：切分词与单词不一致，需人工审查
- 存在 1 条含不可见字符的数据，建议清理
- 存在 87 条含首尾空格的数据，建议 trim
