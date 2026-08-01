INTRO = [
    "你是一个精通英语形态学（Morphology）的专家。请将以下单词按照前缀.词根.后缀的方式用点号 . 进行切分。",
    "必须严格遵守格式：每行仅输出 原始单词 -> 切分后的单词，不要输出任何解释。",
    "",
    "示例：",
    "unbelievable -> un.believ.able",
    "profligate -> pro.flig.ate",
    "",
    "请切分以下单词：",
    "如果真实词根超过 5 个字母，请将其切断成若干可记忆的小块。保证相同模式的词在切分逻辑上 100% 保持一致——含相同字母块/相同词缀的词，边界必须落在同样的位置，不得反复无常。",
]

def build_prompt(words):
    return "\n".join(INTRO + [""] + list(words))
