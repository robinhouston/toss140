#! /bin/bash

if [ ! -d logs ]; then
    echo >&2 "The directory 'logs' doesn't exist. Are you in the wrong directory?"
    exit 1
fi

if [ -e logs/pid ]; then
    pid=$(< logs/pid)
    ps "$pid" | tail +2
    if [ 0 -eq ${PIPESTATUS[0]} ]; then
        echo "The server is already running, with PID $pid"
        exit 1
    fi
fi

dev_appserver.py \
    --port=8082 \
    --datastore_path=data/data.store \
    --history_path=data/data.history \
    toss140 >>"logs/server.log" 2>&1 &

pid=$(jobs -p %%)
echo "$pid" > logs/pid

echo "Server started with PID $pid. Logs in logs/server.log"
