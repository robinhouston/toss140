#!/bin/bash

set -e

if [ ! -e 'toss140/data.py' ]; then
    echo >&2 "You're in the wrong directory"
    exit 1
fi

if [ $# -gt 0 -a "$1" = --date ]; then
    shift
    date="$1"
    shift
else
    date=$(date +%Y-%m-%d_%H%M%S)
fi

if [ "$#" -ne 2 -o \( "$1" != "up" -a "$1" != "down" \) ]; then
    echo >&2 "Usage: $0 (up|down) <hostname> (e.g. 2.latest.toss140.appspot.com, localhost:8082)"
    exit 2
fi

if [ ! -d logs ]; then
    mkdir logs
fi

echo -n "Password for $2: "
trap 'stty echo' EXIT ;# In case the user presses ^C, for example
stty -echo
read password
stty echo
trap - EXIT
echo

export PYTHONPATH=toss140

if [ "$1" = "down" ]; then
    # extra_options is set in the loop, because it contains the entity name
    action="Download"
    preposition=from
else
    extra_options=
    action="Upload"
    preposition=to
fi

for entity in Origin Destination Site Article Tweet; do
    echo
    echo "${action}ing $entity records ${preposition} ${2}"
    echo
    
    if [ "$1" = "down" ]; then
        extra_options="--result_db_filename=logs/${date}_${1}_${2}_${entity}.results.sql3"
    fi
    
    echo "$password" | appcfg.py ${1}load_data --config_file=toss140/loader.py \
      --filename=data/$entity.csv --kind=$entity \
      --log_file="logs/${date}_${1}_${2}_${entity}.log" \
      --db_filename="logs/${date}_${1}_${2}_${entity}.progress.sql3" \
      $extra_options \
      --url=http://${2}/remote_api \
      --email=robin.houston@gmail.com --passin toss140
    echo
done
