import sys
if len(sys.argv) < 2:
    print("Usage: python crlf2lf.py <file>")
    sys.exit(1)
path = sys.argv[1]
data = open(path, 'rb').read()
crlf_count = data.count(b'\r\n')
data = data.replace(b'\r\n', b'\n')
open(path, 'wb').write(data)
print(f"Converted {path}: {crlf_count} CRLF -> LF")
