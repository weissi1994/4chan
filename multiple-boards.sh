#!/usr/bin/env bash
for board in "$@"; do
    python 4chan.py $board
done
