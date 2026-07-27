import sys
sys.path.insert(0, r'F:\code\查词分词\web2mdd')
from app.affix_analyzer import AffixAnalyzer

a = AffixAnalyzer()

with open(r'F:\code\查词分词\web2mdd\test_obscure_words.txt') as f:
    words = [line.strip() for line in f if line.strip()]

header = f'{"Word":28s} {"Result":40s} {"Score":5s} {"Scheme":12s} {"Prefix":15s} {"Suffix":15s} {"#Strats":7s}'
print(header)
print('-' * 125)

total = len(words)
found = 0
for w in words:
    r = a.analyze(w)
    if r:
        p = r['primary']
        if p['scheme'] != 'none':
            found += 1
        n = len(r.get('all_strategies', []))
        out = f'{w:28s} {p["result"]:40s} {p["score"]:<5.1f} {p["scheme"]:12s} {p["prefix"]:15s} {p["suffix"]:15s} {n:<7d}'
        print(out)

print(f'\n总计: {total}, 有分析结果: {found}, 无分析结果: {total - found}')
