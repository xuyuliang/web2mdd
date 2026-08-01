import re

VOWELS = set("aeiou")


def is_consonant(c):
    return c.isalpha() and c.lower() not in VOWELS


def tiled(word, segs):
    return "".join(segs) == word


def segment_starts(segs):
    starts = []
    s = 0
    for seg in segs:
        starts.append(s)
        s += len(seg)
    return starts


def split_suffix(word, segs, suffix):
    """Split `suffix` off the end as its own final segment.

    If the suffix start falls inside a segment, the leftover part of that
    segment is merged into the previous segment (to avoid tiny segments).
    """
    if not word.endswith(suffix) or not segs:
        return segs
    if segs[-1] == suffix:
        return segs
    k = len(word) - len(suffix)
    if k <= 0:
        return segs
    starts = segment_starts(segs)
    if starts[-1] + len(segs[-1]) != len(word):
        return segs
    i = 0
    for idx in range(len(segs)):
        if starts[idx] <= k:
            i = idx
        else:
            break
    if starts[i] == k:
        return segs
    stem_part = word[starts[i]:k]
    if i == 0:
        return [word[:k], suffix]
    return segs[:i - 1] + [segs[i - 1] + stem_part, suffix]


def rule_one_letter(word, segs):
    if len(segs) <= 1:
        return segs
    n = len(segs)
    out = []
    i = 0
    while i < n:
        s = segs[i]
        if len(s) == 1 and out:
            if i == n - 1:
                if s == "y":
                    out.append(s)
                else:
                    out[-1] = out[-1] + s
                i += 1
                continue
            prev = out[-1]
            nxt = segs[i + 1]
            if s == "u" and prev == "di" and nxt == "retic":
                out.append(s + nxt[:2])
                out.append(nxt[2:])
                i += 2
                continue
            if s == "i" and nxt.startswith("fic"):
                out.append(s + nxt)
                i += 2
                continue
            if is_consonant(s):
                if prev[-1] == s:
                    out[-1] = prev + s
                elif nxt and nxt[0] in VOWELS:
                    out.append(s + nxt)
                    i += 2
                    continue
                else:
                    out[-1] = prev + s
                i += 1
                continue
            out[-1] = prev + s
            i += 1
            continue
        out.append(s)
        i += 1
    return out


def rule_ify(word, segs):
    out = []
    i = 0
    n = len(segs)
    while i < n:
        if i + 1 < n and segs[i] == "if" and segs[i + 1] == "y":
            out.append("ify")
            i += 2
            continue
        out.append(segs[i])
        i += 1
    return out


def rule_ation(word, segs):
    if len(segs) >= 2 and segs[-2] == "at" and segs[-1] == "ion":
        return segs[:-2] + ["ation"]
    return segs


def rule_ization(word, segs):
    for suffix in ("ization", "isation"):
        if word.endswith(suffix) and len(word) > len(suffix):
            if segs and segs[-1] == suffix:
                return segs
            k = len(word) - len(suffix)
            starts = segment_starts(segs)
            if k in starts:
                j = starts.index(k)
                if len(segs) - j >= 2:
                    return segs[:j] + [suffix]
                return segs
            return split_suffix(word, segs, suffix)
    return segs


def rule_cata(word, segs):
    out = []
    for s in segs:
        if len(s) >= 8 and s.startswith("cata") and len(s) > 4 and is_consonant(s[4]):
            out.append(s[:4])
            out.append(s[4:])
        else:
            out.append(s)
    return out


def rule_ed(word, segs):
    out = []
    for s in segs:
        if len(s) >= 6 and s.endswith("ed"):
            out.append(s[:-2])
            out.append("ed")
        else:
            out.append(s)
    return out


def rule_ment(word, segs):
    out = []
    for s in segs:
        if len(s) >= 8 and s.endswith("ment"):
            out.append(s[:-4])
            out.append("ment")
        else:
            out.append(s)
    return out


def rule_us(word, segs):
    out = []
    for s in segs:
        if len(s) >= 5 and s.endswith("us"):
            out.append(s[:-2])
            out.append("us")
        else:
            out.append(s)
    return out


def rule_ist(word, segs):
    out = []
    for s in segs:
        if len(s) >= 6 and s.endswith("ist"):
            out.append(s[:-3])
            out.append("ist")
        else:
            out.append(s)
    return out


def rule_tion(word, segs):
    out = []
    for s in segs:
        if len(s) >= 8 and s.endswith("ation"):
            out.append(s[:-5])
            out.append("ation")
        elif len(s) >= 8 and s.endswith("tion"):
            out.append(s[:-4])
            out.append("tion")
        else:
            out.append(s)
    return out


def er_fixable(word, orig_segs):
    if not word.endswith("er"):
        return False
    if len(orig_segs) < 2:
        return False
    last = orig_segs[-1]
    return last == "r" or last.endswith("er")


def rule_er(word, segs, orig_segs):
    if not er_fixable(word, orig_segs):
        return segs
    return split_suffix(word, segs, "er")


def rule_ia(word, segs):
    if word.endswith("ia") and len(word) > 2:
        segs = split_suffix(word, segs, "ia")
    if word == "troubadour" and segs == ["troubadour"]:
        return ["troub", "adour"]
    return segs


def rule_etic(word, segs):
    out = []
    i = 0
    n = len(segs)
    while i < n:
        if i + 1 < n and segs[i] == "net" and segs[i + 1] == "ic":
            if out and out[-1] == "mag":
                out[-1] = "magn"
                out.append("etic")
                i += 2
                continue
            out.append("netic")
            i += 2
            continue
        if i + 1 < n and segs[i] == "et" and segs[i + 1] == "ic":
            out.append("etic")
            i += 2
            continue
        out.append(segs[i])
        i += 1
    return out


def rule_exo(word, segs):
    if not word.startswith("exo"):
        return segs
    if len(segs) < 2 or segs[0] != "ex":
        return segs
    if segs[1][:1] != "o" or len(segs[1]) < 2:
        return segs
    extra = segs[1][1:]
    tail = segs[2:]
    if extra and tail:
        return ["exo"] + [extra + tail[0]] + tail[1:]
    return ["exo"] + ([extra] if extra else []) + tail


def rule_devas(word, segs):
    if segs[:2] == ["devas", "tat"]:
        if segs[2:] == ["ing", "ly"]:
            return ["de", "vast", "ating", "ly"]
        if segs[2:] == ["ing"]:
            return ["de", "vast", "ating"]
        if len(segs) == 2:
            return ["de", "vast"]
    return segs


def rule_iatric(word, segs):
    if word.endswith("iatric") and len(word) > 6:
        return split_suffix(word, segs, "iatric")
    return segs


def apply_rules(word, segs):
    """Apply the rule pipeline in document order. Preserves tiling.

    Returns (new_segs, changed_names). `rule_er` consults the original
    (pre-rule) segmentation to decide whether an "-er" boundary was implied.
    """
    segs = [s.lower() for s in segs]
    word = word.lower()
    orig = list(segs)

    def er_rule(w, s):
        return rule_er(w, s, orig)

    pipeline = [
        ("1letter", rule_one_letter),
        ("ify", rule_ify),
        ("ation", rule_ation),
        ("ization", rule_ization),
        ("cata", rule_cata),
        ("ed", rule_ed),
        ("ment", rule_ment),
        ("us", rule_us),
        ("ist", rule_ist),
        ("tion", rule_tion),
        ("er", er_rule),
        ("ia", rule_ia),
        ("etic", rule_etic),
        ("exo", rule_exo),
        ("devas", rule_devas),
        ("iatric", rule_iatric),
    ]
    changed = []
    for name, fn in pipeline:
        new = fn(word, segs)
        if new != segs and tiled(word, new):
            segs = new
            changed.append(name)
    return segs, changed
