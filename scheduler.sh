#!/bin/bash

if [ $# -lt 7 ]; then
    echo "Usage: bash scheduler.sh <間隔秒數> <帳號> <起站> <終站> <日期> <車次> <座位偏好(n/a/w)> [目標車廂]"
    exit 1
fi

INTERVAL=$1
shift

ATTEMPT=0
while true; do
    ATTEMPT=$((ATTEMPT + 1))
    echo ""
    echo "===== 第 ${ATTEMPT} 次嘗試 ====="
    python main.py "$@"
    EXIT_CODE=$?

    if [ $EXIT_CODE -eq 0 ]; then
        echo "訂票成功!"
        exit 0
    elif [ $EXIT_CODE -eq 2 ]; then
        echo "無座位，${INTERVAL} 秒後重試..."
        sleep "$INTERVAL"
    else
        echo "發生錯誤 (exit ${EXIT_CODE})，停止排程"
        exit 1
    fi
done
