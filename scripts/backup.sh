#! /bin/bash

set -e

date=$(date +%Y-%m-%d_%H%M%S)

echo "Checking for dev appserver..."
lsof -i tcp:8082 && {
    echo >&2
    echo >&2 "Well, *something* is listening on TCP port 8082"
    echo >&2 "I think the dev appserver might be running"
    echo >&2
    exit 1
}

if [ -d "data.older" ]; then
    echo "Deleting directory data.older"
    rm -rf "data.older"
fi
if [ -d "data.old" ]; then
    echo "Renaming data.old to data.older"
    mv "data.old" "data.older"
fi
if [ -d "data" ]; then
    echo "renaming data to data.old"
    mv "data" "data.old"
    mkdir data
fi


echo "Downloading data from www.toss140.net"
scripts/load.sh --date "$date" down www.toss140.net

echo "Starting dev appserver on port 8082"
dev_appserver.py --port=8082 --clear_datastore toss140 >"logs/$date.server-log" 2>&1 &
trap 'kill %%' EXIT
sleep 20

echo "Uploading data to local appserver"
scripts/load.sh --date "$date" up   localhost:8082

sleep 10
echo "Terminating local appserver"
trap - EXIT
kill %%

echo "Finished!"
