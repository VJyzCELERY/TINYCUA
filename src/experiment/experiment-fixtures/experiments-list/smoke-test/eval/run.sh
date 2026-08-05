#!/bin/sh
set -eu

test "$(cat "$1/input.txt")" = "smoke-test"
test "$(cat "$1/output.txt")" = "read: smoke-test"
