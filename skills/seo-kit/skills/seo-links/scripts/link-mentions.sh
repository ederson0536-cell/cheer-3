#!/usr/bin/env bash
# link-mentions.sh — Find unlinked brand mentions
set -e

BRAND="${1:?Usage: link-mentions.sh <brand-name> <your-domain>}"
DOMAIN="${2:?Usage: link-mentions.sh <brand-name> <your-domain>}"

echo "🔍 Finding unlinked mentions of: $BRAND (excluding $DOMAIN)"

if [[ -n "${DATAFORSEO_LOGIN:-}" && -n "${DATAFORSEO_PASSWORD:-}" ]]; then
  # Use DataForSEO SERP API to find mentions
  RESPONSE=$(curl -s -A "Mozilla/5.0 (compatible; SEOKit/1.0)" -X POST "https://api.dataforseo.com/v3/serp/google/organic/live/advanced" \
    -u "${DATAFORSEO_LOGIN}:${DATAFORSEO_PASSWORD}" \
    -H "Content-Type: application/json" \
    -d "[{
      \"keyword\": \"\\\"${BRAND}\\\" -site:${DOMAIN}\",
      \"location_code\": 2840,
      \"language_code\": \"en\",
      \"depth\": 30
    }]")
  
  echo "$RESPONSE" | jq -r '
    .tasks[0].result[0].items[]? | 
    select(.type == "organic") |
    "[\(.rank_absolute)] \(.title)\n  URL: \(.url)\n  Snippet: \(.description // "none")\n"
  ' 2>/dev/null || echo "Error parsing response"
  
else
  echo "No DataForSEO credentials. Generating search queries..."
  echo ""
  echo "Search these manually or via web_search:"
  echo "  1. \"${BRAND}\" -site:${DOMAIN}"
  echo "  2. \"${BRAND}\" review -site:${DOMAIN}"
  echo "  3. \"${BRAND}\" mention -site:${DOMAIN}"
  echo ""
  echo "For each result, check if they link to ${DOMAIN}."
  echo "If they mention you but don't link: easy outreach win."
fi
