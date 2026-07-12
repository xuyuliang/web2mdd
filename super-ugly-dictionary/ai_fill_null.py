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
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "..", "数据资料", "tiny_dict_filled.json")
BATCH_SIZE = 50  # 每批处理词数
MAX_RETRIES = 5  # 增加重试次数
SLEEP_BETWEEN_BATCHES = 3  # 增加批次间隔，避免被限流
SLEEP_ON_RATE_LIMIT = 30  # 遇到限流时等待30秒
REQUEST_TIMEOUT = 60  # 请求超时时间（秒）

# ---------- 初始化客户端 ----------
from openai import OpenAI
client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

# ---------- 读取 JSON ----------
# 检查输出文件是否已存在（用于恢复中断的进度）
if os.path.exists(OUTPUT_FILE):
    print(f"发现已有进度文件: {OUTPUT_FILE}")
    print("将从此文件恢复翻译进度...")
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    # 确保 data 包含所有原始词（如果输出文件不完整）
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        original_data = json.load(f)
    for w in original_data:
        if w not in data:
            data[w] = original_data[w]
else:
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

words = list(data.keys())  # 所有英文词
total = len(words)
print(f"共有 {total} 个词待翻译")

# 统计已翻译数量
translated_count = sum(1 for w in words if data.get(w) is not None and data.get(w) != "")
remaining_count = total - translated_count
print(f"已有翻译: {translated_count} 个")
print(f"待翻译: {remaining_count} 个")

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
            request_start_time = time.time()
            print(f"  -> 正在等待服务器响应...")
            
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "You are a helpful translator."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # 低温度提高确定性
                timeout=REQUEST_TIMEOUT  # 请求超时
            )
            
            request_end_time = time.time()
            request_duration = request_end_time - request_start_time
            
            # 打印服务器反馈信息
            print(f"  -> 服务器响应时间: {request_duration:.2f} 秒")
            if hasattr(response, 'usage') and response.usage:
                print(f"  -> Token 使用: prompt={response.usage.prompt_tokens}, completion={response.usage.completion_tokens}, total={response.usage.total_tokens}")
            if hasattr(response, 'model'):
                print(f"  -> 使用模型: {response.model}")
            if hasattr(response, 'id'):
                print(f"  -> 请求ID: {response.id}")
            result_text = response.choices[0].message.content.strip()
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
            error_msg = str(e)
            print(f"批次翻译失败 (尝试 {attempt+1}/{MAX_RETRIES}): {e}")
            
            # 检测是否是被限流（rate limit）
            if "rate_limit" in error_msg.lower() or "429" in error_msg or "too many requests" in error_msg.lower():
                print(f"检测到限流，等待 {SLEEP_ON_RATE_LIMIT} 秒后重试...")
                time.sleep(SLEEP_ON_RATE_LIMIT)
            else:
                time.sleep(2 ** attempt)  # 指数退避
    # 失败则返回空翻译（保留原词）
    return {w: "" for w in batch_words}

# ---------- 主循环 ----------
# 过滤出需要翻译的词（值为 null 或空字符串的）
words_to_translate = [w for w in words if data.get(w) is None or data.get(w) == ""]
total_to_translate = len(words_to_translate)

if total_to_translate == 0:
    print("所有词都已经有翻译了！")
else:
    print(f"需要翻译: {total_to_translate} 个词")
    print("-" * 50)
    
    # 预估时间：每批约 3 秒
    time_per_batch = 3
    total_batches = (total_to_translate + BATCH_SIZE - 1) // BATCH_SIZE
    
    start_time = time.time()
    batch_num = 0
    
    for i in range(0, total_to_translate, BATCH_SIZE):
        batch_num += 1
        batch = words_to_translate[i:i+BATCH_SIZE]
        
        # 计算进度
        done_count = i + len(batch)
        remaining = total_to_translate - done_count
        
        # 预估剩余时间
        elapsed = time.time() - start_time
        if done_count > 0:
            avg_time_per_word = elapsed / done_count
            remaining_time = remaining * avg_time_per_word
            remaining_min = int(remaining_time // 60)
            remaining_sec = int(remaining_time % 60)
            time_estimate = f"约 {remaining_min}分{remaining_sec}秒"
        else:
            time_estimate = "计算中..."
        
        print(f"[{batch_num}/{total_batches}] 翻译中... 已完成: {done_count}/{total_to_translate}, 剩余: {remaining}, 预估剩余时间: {time_estimate}")
        
        translations = translate_batch(batch)
        
        # 打印本批翻译结果
        print("  本批翻译结果:")
        for w, zh in translations.items():
            print(f"    {w} -> {zh}")
        
        # 更新原数据
        for w, zh in translations.items():
            data[w] = zh
        
        # 每批保存一次，防止中断丢失进度
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"  -> 已保存进度 (共 {done_count} 个词已翻译)")
        
        time.sleep(SLEEP_BETWEEN_BATCHES)
    
    total_time = time.time() - start_time
    total_min = int(total_time // 60)
    total_sec = int(total_time % 60)
    print("-" * 50)
    print(f"全部翻译完成！总耗时: {total_min}分{total_sec}秒")
    print(f"最终文件已保存为: {OUTPUT_FILE}")