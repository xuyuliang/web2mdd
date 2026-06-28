# 换行符统一为 LF 的操作指南

## 背景

在跨平台协作（特别是 Windows + macOS/Linux）中，换行符不一致会导致：
- Git 显示文件全部被修改（`diff` 全是换行符变化）
- AI 编码工具（如 Cline）写入 CRLF，产生脏 diff
- ESLint / Prettier 等工具报告换行符错误

本项目通过 **三重防护** 确保 LF 统一：

| 防护层 | 工具 | 作用 |
|--------|------|------|
| 编辑器层 | `.editorconfig` | 编辑器写入时自动使用 LF |
| Git 层 | `.gitattributes` | Git 提交时自动转 LF，检出时保持 LF |
| 本地 Git 配置 | `core.autocrlf=false` | 禁用 Windows 的 CRLF 自动转换 |
| 手动修复 | `crlf2lf.py` | 紧急修复已存在的 CRLF 文件 |

---

## 标准配置步骤

### 1. 创建 `.editorconfig`

在项目根目录创建：

```ini
root = true

[*]
end_of_line = lf
insert_final_newline = true
charset = utf-8
trim_trailing_whitespace = true

[*.{bat,cmd,ps1}]
end_of_line = crlf

[*.srt]
end_of_line = unset

[*.csv]
end_of_line = unset
```

> VS Code 需要安装 [EditorConfig for VS Code](https://marketplace.visualstudio.com/items?itemName=EditorConfig.EditorConfig) 插件。

### 2. 创建 `.gitattributes`

```gitattributes
# Auto detect text files and normalize to LF
* text=auto eol=lf

# Batch files keep CRLF
*.bat text eol=crlf
*.cmd text eol=crlf
*.ps1 text eol=crlf
```

**关键点**：
- `* text=auto` — 让 Git 自动检测文本文件
- `eol=lf` — 强制 LF（覆盖 `core.autocrlf`）
- `.bat` / `.cmd` / `.ps1` 保留 CRLF（Windows 需要）

### 3. 设置本地 Git 配置

```bash
# 对当前仓库生效（推荐，不影响其他项目）
git config --local core.autocrlf false

# 或全局设置（谨慎，会影响所有仓库）
# git config --global core.autocrlf false
```

> **为什么必须设置？**  
> Windows 的 Git 默认 `core.autocrlf=true`，检出时自动将 LF 转 CRLF，这会**覆盖** `.gitattributes` 的 `eol=lf` 设置。

### 4. 重新规范化现有文件

```bash
# 步骤 A：让 Git 按 .gitattributes 重新规范化索引
git add --renormalize .

# 步骤 B：将 .gitattributes 加入暂存区
git add .gitattributes

# 步骤 C：删除工作目录文件并重新检出（获得 LF）
# Windows PowerShell：
Get-ChildItem -Recurse -Filter *.py | Remove-Item
git checkout -- '*.py'

# 或 Linux/macOS：
# find . -name '*.py' -delete && git checkout -- '*.py'
```

### 5. 验证结果

```bash
# 方法一：Git 自带的 eol 检查
git ls-files --eol

# 期望输出示例（关键看 w/ 列）：
# i/lf    w/lf    attr/text=auto eol=lf    app/main.py
#          ^^^^  工作目录也是 LF，表示成功

# 方法二：Python 字节检查
python -c "
import glob
for f in sorted(glob.glob('**/*.py', recursive=True)):
    data = open(f, 'rb').read()
    crlf = data.count(b'\r\n')
    lf = data.count(b'\n') - crlf
    print(f'{f:40s} CRLF={crlf:3d}  LF={lf:3d}  ', end='')
    print('OK' if crlf == 0 else 'HAS CRLF!')
"

# 方法三：检查 Git 状态
git status --short
```

---

## 紧急修复（文件已经是 CRLF）

如果某个文件已存在 CRLF，使用项目自带的 `crlf2lf.py`：

```bash
python crlf2lf.py app/main.py
```

批量处理所有 `.py` 文件：

```bash
# Windows cmd
for /r %f in (*.py) do python crlf2lf.py "%f"

# 或使用 Python
python -c "
import os, glob
for f in glob.glob('**/*.py', recursive=True):
    os.system(f'python crlf2lf.py \"{f}\"')
"
```

---

## 常见问题 FAQ

### Q1: 设置了 `.gitattributes` 但 `git ls-files --eol` 仍显示 `w/crlf`

**原因**：`core.autocrlf=true` 在检出时将 LF 转回了 CRLF。  
**解决**：运行 `git config --local core.autocrlf false`，然后重新检出文件：

```bash
git config --local core.autocrlf false
# 删除并重新检出
git ls-files -- '*.py' | xargs rm
git checkout -- '*.py'
```

### Q2: `git add --renormalize` 后工作目录没有变化

**说明**：`--renormalize` 只更新 Git 索引，不修改工作目录。  
**解决**：删除工作目录文件后重新检出（见上方步骤 C）。

### Q3: Cline 等 AI 工具写入的文件仍是 CRLF

**原因**：Cline 继承 VS Code 的换行符设置，如果 VS Code 全局设为 CRLF，Cline 也会写入 CRLF。  
**解决**：
1. 确保 `.editorconfig` 存在且生效（安装 EditorConfig 插件）
2. VS Code 设置中检查：`"files.eol": "\n"`
3. 或者在 `.vscode/settings.json` 中设置：
   ```json
   {
       "files.eol": "\n"
   }
   ```

### Q4: 误将 .gitattributes 设为 `eol=crlf` 导致文件损坏

**解决**：修正 `.gitattributes`，然后重新规范化：

```bash
# 修正后
git add --renormalize .
# 如果还有问题，强制重置
git rm --cached -r .
git reset --hard
```

### Q5: 如何检查一个文件当前的换行符？

```bash
# 方法 1：file 命令 (Linux/macOS/Git Bash)
file app/main.py

# 方法 2：十六进制查看 (Windows)
certutil -encodehex app/main.py temp.hex
findstr "0d0a" temp.hex  # 查找 CRLF(0d0a)

# 方法 3：Python
python -c "d=open('app/main.py','rb').read(); print(f'CRLF={d.count(b\"\\r\\n\")}, LF={d.count(b\"\\n\")-d.count(b\"\\r\\n\")}')"
```

---

## 完整工作流（一键修复）

以下是在现有项目上**从头修复**的完整命令（已安装 Python）：

```bash
# 1. 创建 .editorconfig（如果不存在）
# 手动复制上方内容

# 2. 创建 .gitattributes
echo * text=auto eol=lf> .gitattributes
echo *.bat text eol=crlf>> .gitattributes
echo *.cmd text eol=crlf>> .gitattributes
echo *.ps1 text eol=crlf>> .gitattributes

# 3. 关闭 Windows 的 CRLF 转换
git config --local core.autocrlf false

# 4. 重新规范化所有文件
git add --renormalize .
git add .gitattributes

# 5. 删除所有文本文件并重新检出
# （此处按实际项目扩展名调整）
git ls-files -- '*.py' '*.js' '*.ts' '*.json' '*.md' '*.yml' '*.yaml' '*.html' '*.css' '*.scss' | xargs rm
git checkout -- .

# 6. 验证
git ls-files --eol | grep -E '\.(py|js|ts|json|md)$'

# 7. 提交
git commit -m "chore: 统一换行符为 LF"
```

---

## 实战经验：本项目实际执行记录

> 以下记录换行符统一在实际项目中执行的过程、遇到的问题和解决方案。

### 背景

本项目已有 `.editorconfig`、`.gitattributes`、`core.autocrlf=false` 三重防护。但历史文件仍遗留 CRLF（共约 47 个文件）。

### 过程

#### 尝试 A：先 `git add --renormalize` 再 `git checkout`

```powershell
# 更新索引
git add --renormalize .

# ❌ 错误的做法：Get-ChildItem -Recurse | Remove-Item
# 这会删除 venv/、未跟踪的新文件等，且无法恢复！
```

**教训**：不要直接用 `Get-ChildItem -Recurse` 删除全部文件。

#### 成功方案：PowerShell 筛选 + git checkout（对大部分文件有效）

```powershell
# 只删除有 w/crlf 的文本文件，排除 .bat/.cmd/.ps1 和二进制文件
git ls-files --eol | ForEach-Object {
    if ($_ -match "w/crlf") {
        $fields = $_ -split "`t"
        $file = $fields[-1]
        if ($file -notlike "*.bat" -and $file -notlike "*.cmd" -and $file -notlike "*.ps1") {
            Remove-Item -Path $file -ErrorAction SilentlyContinue
        }
    }
}
git checkout -- .
```

**效果**：大部分文件成功从 `w/crlf` 转为 `w/lf` ✅

#### 遗留问题：Unicode 文件名文件

部分文件（中文名）在 `git ls-files --eol` 中仍显示 `w/crlf`，但实际已删除后重新检出，却**没有被修复**。原因是：

1. Git 默认 `core.quotepath=true`，中文文件名在输出中显示为八进制转义（如 `\346\225\260` 表示 `数`）
2. PowerShell 的 `Remove-Item` 可能无法正确识别带 Unicode 路径的文件
3. `git checkout -- .` 从索引恢复时，这些文件的索引可能未正确规范化

#### 最终方案：Python 直接转换

对遗留文件使用 Python 直接修复（避开 shell 编码问题）：

```python
"""修复 Git 跟踪文本文件中的 CRLF"""
import subprocess, os, re

def decode_git_filename(raw: str) -> str:
    """解码 Git 的八进制转义文件名（如 \\350\\247\\243 -> 解）"""
    def replace_octal(m):
        octals = m.group(0).split("\\")[1:]
        bytes_seq = bytes(int(o, 8) for o in octals if o)
        return bytes_seq.decode("utf-8")
    return re.sub(r'(?:\\[0-7]{3})+', replace_octal, raw)

result = subprocess.run(["git", "ls-files", "--eol"],
    capture_output=True, text=True)

for line in result.stdout.strip().split("\n"):
    if "w/crlf" not in line:
        continue
    parts = line.split("\t")
    filename = decode_git_filename(parts[-1].strip().strip('"'))
    if filename.endswith((".bat", ".cmd", ".ps1")) or "i/-text" in line:
        continue
    if not os.path.exists(filename):
        continue
    data = open(filename, "rb").read()
    crlf_count = data.count(b"\r\n")
    if crlf_count > 0:
        data = data.replace(b"\r\n", b"\n")
        open(filename, "wb").write(data)
        print(f"Fixed: {filename} ({crlf_count} CRLF -> LF)")
```

**效果**：所有 16 个 Unicode 文件名文件被成功修复 ✅

### 最终结果

| 类别 | 文件数 | 结果 |
|------|--------|------|
| `.py` 文件 | 全部 | 原本已是 LF ✅ |
| 英文名文本文件 | 30+ | PowerShell + checkout 修复 ✅ |
| 中文名文本文件 | 16 | Python 直接转换修复 ✅ |
| `.bat` 文件 | `start.bat` | 保留 CRLF ✅ |
| 二进制文件 (png/gif/xlsx等) | 全部 | 未受影响 ✅ |
| `venv/` + 未跟踪新文件 | 不受影响 | 完好无损 ✅ |

### 关键经验总结

1. ⚠️ **不要**直接用 `Get-ChildItem -Recurse` + `Remove-Item` 再 `git checkout`。这会删除 `.gitignore` 中的文件（如 `venv/`）和未跟踪的新文件，且无法恢复。

2. 🎯 **正确做法**：通过 `git ls-files --eol` 精确筛选有 `w/crlf` 的文本文件，只操作这些文件。

3. 🈳 **Unicode 文件名问题**：`core.quotepath=true`（默认）时，Git 输出中文名为八进制转义。PowerShell 处理这类路径可能失败。Python 可以直接解码修复。

4. 📝 **建议的工作流（综合版）**：
   ```powershell
   # 1. 确保配置正确
   git config --local core.autocrlf false
   git add --renormalize .
   
   # 2. 用 Python 统一修复（处理 Unicode 文件名健壮）
   python -c "
   import subprocess, os, re
   def decode_git_filename(raw):
       def replace_octal(m):
           octals = m.group(0).split('\\\\')[1:]
           return bytes(int(o,8) for o in octals if o).decode('utf-8')
       return re.sub(r'(?:\\\\[0-7]{3})+', replace_octal, raw)
   r = subprocess.run(['git','ls-files','--eol'], capture_output=True, text=True)
   for l in r.stdout.strip().split('\n'):
       if 'w/crlf' not in l: continue
       f = decode_git_filename(l.split('\t')[-1].strip().strip('\"'))
       if f.endswith(('.bat','.cmd','.ps1')) or 'i/-text' in l: continue
       d = open(f,'rb').read()
       c = d.count(b'\r\n')
       if c>0: open(f,'wb').write(d.replace(b'\r\n',b'\n')); print(f'Fixed: {f} ({c})')
   "
   
   # 3. 验证
   git ls-files --eol | findstr "w/crlf"
   git status --short
   ```

---

## 参考

- [Git - gitattributes Documentation](https://git-scm.com/docs/gitattributes)
- [EditorConfig](https://editorconfig.org/)
- [Dealing with line endings (GitHub)](https://docs.github.com/en/get-started/getting-started-with-git/configuring-git-to-handle-line-endings)
