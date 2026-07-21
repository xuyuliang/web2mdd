#!/bin/bash
set -e

cd "$(dirname "$0")"

PID_FILE=".server.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "❌ 未找到 PID 文件，服务可能未在运行"
    exit 1
fi

PID=$(cat "$PID_FILE")

if kill -0 "$PID" 2>/dev/null; then
    echo "正在停止服务（PID: $PID）..."
    kill "$PID"
    sleep 1
    # 如果还没退出，强制终止
    if kill -0 "$PID" 2>/dev/null; then
        kill -9 "$PID"
    fi
    echo "✅ 服务已停止"
else
    echo "⚠️  进程 $PID 不存在，清理残留文件"
fi

rm -f "$PID_FILE"
