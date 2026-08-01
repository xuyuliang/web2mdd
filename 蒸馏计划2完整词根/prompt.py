INTRO = [
    "你是一位精通英语形态学（Morphology）的专家。下面给你一组英文单词，请把它们按“前缀.词根.后缀”的结构切分开，用点号 . 分隔。",
    "",
    "输出格式务必统一：每行先写原单词，再写切分结果，中间用 -> 连接，不要加任何解释。",
    "例如：",
    "unbelievable -> un.believ.able",
    "bibliography -> biblio.graphy",
    "inculcate -> in.culc.ate",
    "",
    "请切分下面的单词。注意两点：",
    "- 要按真实的词源来切，找出真正的词根和前后缀。",
    "- 切出来的各部分按顺序拼起来，必须和原单词完全一样（一个字母都不能多，也不能少）。",
    "",
]

def build_prompt(words):
    return "\n".join(INTRO + list(words))
