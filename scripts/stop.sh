#! /bin/bash

set -e

if [ ! -e logs/pid ]; then
    echo >&2 "File logs/pid does not exist"
    exit 1
fi

pid=$(< logs/pid)
echo "Sending SIGTERM to process $pid"
kill $pid
sleep 1

ps "$pid" | tail +2
if [ 0 -ne ${PIPESTATUS[0]} ]; then
    echo "Server stopped"
else
    echo "Server is still running!"
    exit 1
fi

rm logs/pid
