#!/bin/sh
set -eu

exec python /eval/check.py "$1" /result
