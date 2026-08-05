#!/bin/sh
set -eu

if [ "$#" -eq 0 ]; then
    echo 'usage: sh .agent_scripts/search.sh "query"' >&2
    exit 2
fi

endpoint=${SEARXNG_URL:-${SEARXNG_BASE_URL:-http://searxng:8080}}
endpoint=${endpoint%/}
case "$endpoint" in
    */search) ;;
    *) endpoint="$endpoint/search" ;;
esac

curl --fail --silent --show-error --get \
    --data-urlencode "q=$*" \
    --data-urlencode "format=json" \
    "$endpoint" |
    jq -r '.results[:10] | to_entries[] | "\(.key + 1). \(.value.title // "(untitled)")\n\(.value.url // "")\n\(.value.content // "")\n"'
