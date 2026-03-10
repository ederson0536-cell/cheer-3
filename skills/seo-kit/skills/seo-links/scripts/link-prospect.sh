#!/usr/bin/env bash
# link-prospect.sh — Find resource pages to get listed on
set -e

KEYWORD="${1:?Usage: link-prospect.sh <niche-keyword> [--limit 20]}"
LIMIT="${3:-20}"

echo "🎯 Prospecting resource pages for: $KEYWORD"

if [[ -n "${DATAFORSEO_LOGIN:-}" && -n "${DATAFORSEO_PASSWORD:-}" ]]; then
  QUERIES=(
    "${KEYWORD} best tools"
    "${KEYWORD} resources list"
    "${KEYWORD} top software"
    "${KEYWORD} alternatives"
    "${KEYWORD} ultimate guide"
  )
  
  for Q in "${QUERIES[@]}"; do
    echo ""
    echo "--- Query: $Q ---"
    RESPONSE=$(curl -s -A "Mozilla/5.0 (compatible; SEOKit/1.0)" -X POST "https://api.dataforseo.com/v3/serp/google/organic/live/advanced" \
      -u "${DATAFORSEO_LOGIN}:${DATAFORSEO_PASSWORD}" \
      -H "Content-Type: application/json" \
      -d "[{
        \"keyword\": \"${Q}\",
        \"location_code\": 2840,
        \"language_code\": \"en\",
        \"depth\": 10
      }]")
    
    echo "$RESPONSE" | jq -r '
      .tasks[0].result[0].items[]? | 
      select(.type == "organic") |
      "  [\(.rank_absolute)] \(.title)\n    \(.url)\n"
    ' 2>/dev/null
  done
  
else
  echo "No DataForSEO. Search these queries manually:"
  echo ""
  echo "  1. ${KEYWORD} best tools"
  echo "  2. ${KEYWORD} resources"
  echo "  3. ${KEYWORD} top software list"
  echo "  4. ${KEYWORD} alternatives"
  echo "  5. ${KEYWORD} ultimate guide roundup"
  echo ""
  echo "Look for pages that curate multiple links."
  echo "Check if you're already listed."
  echo "If not, pitch for inclusion."
fi
