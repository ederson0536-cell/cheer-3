#!/usr/bin/env bash
# link-mine.sh — Mine competitor backlinks via DataForSEO or web search fallback
set -e

COMPETITOR="${1:?Usage: link-mine.sh <competitor-domain> [--limit 50]}"
LIMIT=50
YOUR_DOMAIN=""

while [[ $# -gt 1 ]]; do
  case "$2" in
    --limit) LIMIT="$3"; shift 2 ;;
    --domain) YOUR_DOMAIN="$3"; shift 2 ;;
    *) shift ;;
  esac
done

echo "🔗 Mining backlinks for: $COMPETITOR (limit: $LIMIT)"

if [[ -n "${DATAFORSEO_LOGIN:-}" && -n "${DATAFORSEO_PASSWORD:-}" ]]; then
  echo "Using DataForSEO Backlinks API..."
  
  RESPONSE=$(curl -s -A "Mozilla/5.0 (compatible; SEOKit/1.0)" -X POST "https://api.dataforseo.com/v3/backlinks/backlinks/live" \
    -u "${DATAFORSEO_LOGIN}:${DATAFORSEO_PASSWORD}" \
    -H "Content-Type: application/json" \
    -d "[{
      \"target\": \"${COMPETITOR}\",
      \"mode\": \"as_is\",
      \"limit\": ${LIMIT},
      \"order_by\": [\"rank,desc\"],
      \"filters\": [\"dofollow\",\"=\",true]
    }]")
  
  # Check for API errors
  STATUS_CODE=$(echo "$RESPONSE" | jq -r ".tasks[0].status_code // 0")
  if [[ "$STATUS_CODE" != "20000" ]]; then
    STATUS_MSG=$(echo "$RESPONSE" | jq -r ".tasks[0].status_message // "unknown"")
    echo "DataForSEO Backlinks API error: $STATUS_MSG"
    echo "Falling back to web search..."
    echo ""
    echo "Search these queries to find sites linking to $COMPETITOR:"
    echo "  1. "${COMPETITOR}" resources"
    echo "  2. "${COMPETITOR}" best tools"
    echo "  3. "${COMPETITOR}" roundup"
    echo "  4. "${COMPETITOR}" review"
    exit 0
  fi
  echo "$RESPONSE" | jq -r '
    .tasks[0].result[0].items[]? | 
    "DR: \(.domain_from_rank // "?") | \(.url_from) | Anchor: \(.anchor // "none") | Type: \(.type // "unknown")"
  ' 2>/dev/null || echo "Error parsing DataForSEO response"
  
  # Check for API errors
  STATUS_CODE=$(echo "$RESPONSE" | jq -r ".tasks[0].status_code // 0")
  if [[ "$STATUS_CODE" != "20000" ]]; then
    STATUS_MSG=$(echo "$RESPONSE" | jq -r ".tasks[0].status_message // "unknown"")
    echo "DataForSEO Backlinks API error: $STATUS_MSG"
    echo "Falling back to web search..."
    echo ""
    echo "Search these queries to find sites linking to $COMPETITOR:"
    echo "  1. "${COMPETITOR}" resources"
    echo "  2. "${COMPETITOR}" best tools"
    echo "  3. "${COMPETITOR}" roundup"
    echo "  4. "${COMPETITOR}" review"
    exit 0
  fi
  TOTAL=$(echo "$RESPONSE" | jq -r '.tasks[0].result[0].total_count // 0')
  echo ""
  echo "Total backlinks found: $TOTAL (showing top $LIMIT)"
  
else
  echo "No DataForSEO credentials. Using web search fallback..."
  echo ""
  echo "Searching for resource pages linking to $COMPETITOR..."
  echo "---"
  
  QUERIES=(
    "\"${COMPETITOR}\" resources"
    "\"${COMPETITOR}\" best tools"
    "\"${COMPETITOR}\" roundup"
    "\"${COMPETITOR}\" review"
    "\"${COMPETITOR}\" alternative"
  )
  
  for Q in "${QUERIES[@]}"; do
    echo "Query: $Q"
    echo "(Run this in your browser or via web_search tool)"
    echo ""
  done
  
  echo "Tip: For full backlink data, set up DataForSEO (\$50/month)."
  echo "Without it, you can still find resource pages and roundups manually."
fi
