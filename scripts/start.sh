#! /bin/bash

dev_appserver.py \
    --port=8082 \
    --datastore_path=data/data.store \
    --history_path=data/data.history \
    toss140 >>"logs/server.log" 2>&1 &

echo "Server started. Logs in logs/server.log"
