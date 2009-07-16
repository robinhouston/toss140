#!/bin/bash

set -e

if [ ! -e 'toss140/data.py' ]; then
	echo >&2 "You're in the wrong directory"
	exit 1
fi

if [ "$#" -ne 2 -o \( "$1" != "up" -a "$1" != "down" \) ]; then
	echo >&2 "Usage: $0 (up|down) <hostname> (e.g. 2.latest.toss140.appspot.com, localhost:8082)"
	exit 2
fi


export PYTHONPATH=toss140

for entity in Origin Site Article Tweet; do
	appcfg.py ${1}load_data --config_file=toss140/loader.py \
	  --filename=data/$entity.csv --kind=$entity \
	  --url=http://${2}/remote_api \
	  --email=robin.houston@gmail.com toss140
done
