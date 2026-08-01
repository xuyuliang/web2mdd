from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
KEY_FILE = BASE_DIR / "agnes的apikey.key"
OUT_DIR = BASE_DIR / "output"
OUT_DIR.mkdir(exist_ok=True)

def load_key():
    lines = KEY_FILE.read_text(encoding="utf-8").strip().splitlines()
    base = lines[0].split("base url ")[1].strip()
    key = lines[1].strip()
    return base, key

BASE_URL, API_KEY = load_key()
PROXY = "http://127.0.0.1:1080"
MODEL = "agnes-2.0-flash"
TEMPERATURE = 0.0
MAX_TOKENS = 3000
BATCH_SIZE = 10
MAX_RETRIES = 3
RETRY_BACKOFF = 4

COCA_PATH = BASE_DIR.parent / "数据资料" / "oldCOCA60000.txt"
RANGE_LO = 10000
RANGE_HI = 40000

WORDS_ALL = OUT_DIR / "words_all.txt"
PILOT_WORDS = OUT_DIR / "pilot_words.txt"
PILOT_RAW = OUT_DIR / "pilot_raw.jsonl"
FULL_RAW = OUT_DIR / "llm_splits_raw.jsonl"
FULL_RAW_2 = OUT_DIR / "llm_splits_raw_2.jsonl"
CLEAN = OUT_DIR / "llm_splits_clean.jsonl"
INVALID = OUT_DIR / "llm_splits_invalid.jsonl"
REPORT = OUT_DIR / "report.txt"

TRAIN_JSONL = OUT_DIR / "train.jsonl"
VAL_JSONL = OUT_DIR / "val.jsonl"
TEST_JSONL = OUT_DIR / "test.jsonl"
MODEL_NPZ = OUT_DIR / "model.npz"
EVAL_REPORT = OUT_DIR / "eval_report.txt"

SEED = 42
SPLIT_TRAIN = 0.90
SPLIT_VAL = 0.05
