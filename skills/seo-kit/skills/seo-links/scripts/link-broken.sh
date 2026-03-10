#!/usr/bin/env bash
# link-broken.sh — Find broken link building opportunities
set -e

KEYWORD="${1:?Usage: link-broken.sh <niche-keyword> [--limit 30]}"
LIMIT="${3:-30}"

echo "🔨 Finding broken link opportunities for: $KEYWORD"

if [[ -n "${DATAFORSEO_LOGIN:-}" && -n "${DATAFORSEO_PASSWORD:-}" ]]; then
  # Find resource pages first
  RESPONSE=$(curl -s -A "Mozilla/5.0 (compatible; SEOKit/1.0)" -X POST "https://api.dataforseo.com/v3/serp/google/organic/live/advanced" \
    -u "${DATAFORSEO_LOGIN}:${DATAFORSEO_PASSWORD}" \
    -H "Content-Type: application/json" \
    -d "[{
      \"keyword\": \"${KEYWORD} resources OR tools OR guide\",
      \"location_code\": 2840,
      \"language_code\": \"en\",
      \"depth\": ${LIMIT}
    }]")
  
  echo "Resource pages found:"
  echo "$RESPONSE" | jq -r '
    .tasks[0].result[0].items[]? | 
    select(.type == "organic") |
    "\(.url)"
  ' 2>/dev/null | while read -r URL; do
    echo ""
    echo "Checking: $URL"
    # Check for dead outbound links
    LINKS=$(curl -s -A "Mozilla/5.0 (compatible; SEOKit/1.0)"L --max-time 10 "$URL" 2>/dev/null | grep -oP 'href="\K[^"]+' | grep '^http' | sort -u | head -20)
    for LINK in $LINKS; do
      STATUS=$(curl -s -A "Mozilla/5.0 (compatible; SEOKit/1.0)"I --max-time 5 -o /dev/null -w "%{http_code}" "$LINK" 2>/dev/null || echo "000")
      if [[ "$STATUS" == "404" || "$STATUS" == "410" || "$STATUS" == "000" ]]; then
        echo "  ❌ DEAD ($STATUS): $LINK"
      fi
    done
  done
  
else
  echo "No DataForSEO. Generating search queries for resource pages..."
  echo ""
  echo "  1. ${KEYWORD} resources"
  echo "  2. ${KEYWORD} best tools"  
  echo "  3. ${KEYWORD} ultimate guide"
  echo ""
  echo "Check each page's outbound links for 404s."
  echo "Offer your content as a replacement."
fi
