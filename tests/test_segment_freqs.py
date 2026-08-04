"""改动 A：segment-freqs 并入第二语料 rules_clean 的口径测试。

验证：
  1. 共存词 anki 优先（rules 跳过共存词）。
  2. rules 单段整词跳过。
  3. anki 单段词照计。
  4. 段位置定位 first/last/middle、每词每段去重计 1 次、段 .lower()。
"""
import json
import os
import sys
import tempfile

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "scripts"))
import build_segment_freqs as bsf


@pytest.fixture()
def env():
    tmp = tempfile.mkdtemp()
    rules_path = os.path.join(tmp, "rules.jsonl")
    return rules_path


def _write_rules(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def test_coexist_anki_priority(env):
    rules = [{"word": "alpha", "segments": ["al", "pha"]}]
    _write_rules(env, rules)
    splits = {"alpha": {"split": "al.pha", "source": "field3"}}
    out = bsf.build(splits, env, {"alpha"})
    # 共存词只按 anki 计一次：al.count==1（不因 rules 再累加）
    assert out["al"]["count"] == 1
    assert out["pha"]["count"] == 1


def test_rules_only_fills_missing(env):
    rules = [{"word": "bravo", "segments": ["bra", "vo"]}]
    _write_rules(env, rules)
    splits = {"alpha": {"split": "al.pha", "source": ""}}
    out = bsf.build(splits, env, {"alpha"})
    assert out["bra"]["count"] == 1
    assert out["vo"]["count"] == 1
    # rules 词也被计入 total words（positions 累计）
    assert out["bra"]["positions"]["first"] == 1


def test_rules_single_seg_skipped(env):
    rules = [{"word": "alone", "segments": ["alone"]},
             {"word": "beta", "segments": ["be", "ta"]}]
    _write_rules(env, rules)
    out = bsf.build({}, env, set())
    assert "alone" not in out
    assert out["be"]["count"] == 1


def test_anki_single_seg_kept(env):
    _write_rules(env, [])
    splits = {"cat": {"split": "cat", "source": ""}}
    out = bsf.build(splits, env, {"cat"})
    assert out["cat"]["count"] == 1
    # 单段 i==0 -> first（原逻辑如此，不额外计 last）
    assert out["cat"]["positions"]["first"] == 1
    assert out["cat"]["positions"]["last"] == 0


def test_position_mapping_and_dedup(env):
    rules = [{"word": "united", "segments": ["Un", "it", "Ed"]},
             {"word": "redo", "segments": ["re", "do", "re"]}]
    _write_rules(env, rules)
    out = bsf.build({}, env, set())
    assert out["un"]["positions"]["first"] == 1
    assert out["it"]["positions"]["middle"] == 1
    assert out["ed"]["positions"]["last"] == 1
    # re 在同一词出现 2 次，去重计 1
    assert out["re"]["count"] == 1


def test_count_equals_distinct_words(env):
    rules = [{"word": "w1", "segments": ["ax", "by"]},
             {"word": "w2", "segments": ["ax", "cz"]}]
    _write_rules(env, rules)
    out = bsf.build({}, env, set())
    assert out["ax"]["count"] == 2
    assert out["by"]["count"] == 1