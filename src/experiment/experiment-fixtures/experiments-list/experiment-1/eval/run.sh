#!/bin/sh
set -eu

output=/agent-output/agent.stdout.log
if grep -F '"type":"text"' "$output" | grep -F '"text":"Hello Reply"' >/dev/null ||
  sed 's/^[[:space:]]*//; s/[[:space:]]*$//' "$output" | grep -Fx 'Hello Reply' >/dev/null ||
  grep -F 'Hello Reply[response] completed' "$output" >/dev/null; then
  points=1
  evidence='exact Hello Reply response found'
else
  points=0
  evidence='exact Hello Reply response not found'
fi

cat > /result/score.json <<EOF
{"categories":{"exact_response":{"points":$points,"max_points":1,"evidence":["$evidence"]}},"total":$points,"pass_threshold":1,"critical_categories":["exact_response"]}
EOF

test "$points" = 1
