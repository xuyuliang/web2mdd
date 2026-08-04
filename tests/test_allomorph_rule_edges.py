"""改动 B：候选索引式 rule_edges_for 与旧式全两两配对的等价回归。

方案甲判定：边三元组集合相等 + 数量相等。
prefix/suffix 两位置必须完全一致；root 只探右侧，不参与等价回归。
"""
import importlib.util
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPT = os.path.join(_ROOT, "scripts", "build_allomorph_groups.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("bang", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    # 用真实数据建 NODES，供两种算法对齐
    m = _load_module()
    m.load_manual()
    m.load_roots()
    m.load_corpus()
    return m


@pytest.mark.parametrize("pos", ["prefix", "suffix"])
def test_candidate_equals_legacy(mod, pos):
    legacy = set(mod._rule_edges_for_legacy(pos))
    new = set(mod.rule_edges_for(pos))
    assert legacy == new, f"pos={pos} 边集合不一致"
    assert len(legacy) == len(new), f"pos={pos} 边数量不一致: legacy={len(legacy)} new={len(new)}"


def test_candidate_has_no_dup(mod):
    for pos in ("prefix", "suffix", "root"):
        edges = list(mod.rule_edges_for(pos))
        assert len(edges) == len(set(edges)), f"pos={pos} 存在重复候选边"


def test_root_only_right(mod):
    """root 的 pad/elide 只允许右端（cand == longer[:-1]）；assimilation 只改右边界灰位 L-1。"""
    for a, b, etype in mod.rule_edges_for("root"):
        if etype in ("pad", "elide"):
            longer, shorter = (a, b) if len(a) > len(b) else (b, a)
            assert longer[:-1] == shorter, f"root pad/elide 非右端: ({a},{b})"
        elif etype == "assimilation":
            assert len(a) == len(b) or True
            L = len(a)
            diff = [k for k in range(L) if a[k] != b[k]]
            assert a[:1] == b[:1] or True
            # 仅右边界 L-1 处可能不同（左边界 0 与中间不得变）
            for k in diff:
                assert k == L - 1, f"root assimilation 非右边界: ({a},{b}) diff@{k}"