import json
import os
import time

# ---------- 配置 ----------
# 从文件读取 API Key
KEY_FILE = os.path.join(os.path.dirname(__file__), "minimax.key")
with open(KEY_FILE, "r", encoding="utf-8") as f:
    API_KEY = f.read().strip()

BASE_URL = "https://zhenze-huhehaote.cmecloud.cn/api/coding/v1"
MODEL = "MiniMax-M2.5"

INPUT_FILE = os.path.join(os.path.dirname(__file__), "..", "数据资料", "tiny_dict_null.json")
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "test_output_100.json")
BATCH_SIZE = 50  # 每批处理词数
MAX_RETRIES = 3
SLEEP_BETWEEN_BATCHES = 1  # 秒

# ---------- 初始化客户端 ----------
from openai import OpenAI
client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

# ---------- 读取 JSON ----------
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

words = list(data.keys())[:100]  # 只取前100个词
total = len(words)
print(f"共有 {total} 个词待翻译")

# ---------- 分批翻译函数 ----------
def translate_batch(batch_words):
    """调用 API 翻译一批词，返回 {英文: 中文} 字典"""
    prompt = (
        "你是一个翻译助手。请将以下英文单词逐一翻译成最常见的一个中文词语。\n"
        "要求：\n"
        "1. 只输出一个中文词语，不要输出解释、例句、多个义项。\n"
        "2. 如果单词有多个意思，只取最常用的那个。\n"
        "3. 输出格式必须是严格的 JSON 对象，键为英文单词，值为对应中文词语。\n"
        "4. 只输出 JSON，不要有任何额外文字。\n\n"
        "英文单词列表：\n" + "\n".join(batch_words)
    )
    
    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "You are a helpful translator."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1  # 低温度提高确定性
            )
            print(f"响应对象: {response}")
            print(f"Choices: {response.choices}")
            if response.choices:
                msg = response.choices[0].message
                print(f"Message: {msg}")
                print(f"Message content: {repr(msg.content)}")
                result_text = msg.content.strip() if msg.content else ""
            else:
                result_text = ""
            print(f"API 返回内容: {repr(result_text[:200])}")
            if not result_text:
                raise Exception("API 返回内容为空")
            # 去除 Markdown 代码块格式
            result_text = result_text.strip()
            if result_text.startswith("```"):
                # 去除 ```json 和 ```
                lines = result_text.split("\n")
                # 找到 JSON 内容的开始和结束
                start_idx = 0
                end_idx = len(lines)
                for i, line in enumerate(lines):
                    if line.strip().startswith("{"):
                        start_idx = i
                        break
                for i in range(len(lines) - 1, -1, -1):
                    if lines[i].strip().endswith("}"):
                        end_idx = i + 1
                        break
                result_text = "\n".join(lines[start_idx:end_idx])
            # 解析 JSON
            translation = json.loads(result_text)
            # 确保返回的键都在 batch_words 中（过滤可能的额外键）
            return {k: translation.get(k, "") for k in batch_words}
        except Exception as e:
            import traceback
            print(f"批次翻译失败 (尝试 {attempt+1}/{MAX_RETRIES}): {e}")
            traceback.print_exc()
            time.sleep(2 ** attempt)  # 指数退避
    # 失败则返回空翻译（保留原词）
    return {w: "" for w in batch_words}

# ---------- 主循环 ----------
filled_data = {}
for i in range(0, total, BATCH_SIZE):
    batch = words[i:i+BATCH_SIZE]
    print(f"正在翻译第 {i+1} ~ {min(i+BATCH_SIZE, total)} 个词...")
    translations = translate_batch(batch)
    filled_data.update(translations)
    print(f"已保存进度")
    time.sleep(SLEEP_BETWEEN_BATCHES)

# 保存结果
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(filled_data, f, ensure_ascii=False, indent=2)

print("\n翻译完成！结果已保存到:", OUTPUT_FILE)
print("\n翻译结果预览：")
for k, v in list(filled_data.items())[:20]:
    print(f"  {k} -> {v}")