#!/usr/bin/env bash
# link-internal.sh — Audit internal link structure
set -e

DOMAIN="${1:?Usage: link-internal.sh <your-domain> [--sitemap URL]}"
SITEMAP="${3:-https://${DOMAIN}/sitemap.xml}"

echo "🕸️ Auditing internal links for: $DOMAIN"
echo "Sitemap: $SITEMAP"

# Fetch sitemap and extract URLs
echo ""
echo "Fetching sitemap..."
URLS=$(curl -s -A "Mozilla/5.0 (compatible; SEOKit/1.0)"L "$SITEMAP" 2>/dev/null | grep -oP '<loc>\K[^<]+' | head -50)

if [[ -z "$URLS" ]]; then
  echo "No sitemap found or empty. Trying sitemap_index..."
  URLS=$(curl -s -A "Mozilla/5.0 (compatible; SEOKit/1.0)"L "$SITEMAP" 2>/dev/null | grep -oP '<loc>\K[^<]+' | head -5 | while read -r SUB; do
    curl -s -A "Mozilla/5.0 (compatible; SEOKit/1.0)"L "$SUB" 2>/dev/null | grep -oP '<loc>\K[^<]+' | head -20
  done)
fi

if [[ -z "$URLS" ]]; then
  echo "Could not fetch sitemap. Provide URL manually with --sitemap"
  exit 1
fi

URL_COUNT=$(echo "$URLS" | wc -l)
echo "Found $URL_COUNT pages"
echo ""

# Check internal links for each page
echo "Analyzing internal link structure..."
echo "======================================"

declare -A INBOUND_COUNT

# First pass: count inbound links
while IFS= read -r PAGE; do
  SLUG=$(echo "$PAGE" | sed "s|https://${DOMAIN}||")
  INBOUND_COUNT["$SLUG"]=0
done <<< "$URLS"

while IFS= read -r PAGE; do
  BODY=$(curl -s -A "Mozilla/5.0 (compatible; SEOKit/1.0)"L --max-time 10 "$PAGE" 2>/dev/null)
  INTERNAL_LINKS=$(echo "$BODY" | grep -oP "href=\"\K[^\"]*" | grep -E "^/|^https://${DOMAIN}" | sed "s|https://${DOMAIN}||" | sort -u)
  
  SLUG=$(echo "$PAGE" | sed "s|https://${DOMAIN}||")
  LINK_COUNT=$(echo "$INTERNAL_LINKS" | grep -c . || true)
  
  echo "📄 ${SLUG} → ${LINK_COUNT} outbound internal links"
  
  # Count inbound
  while IFS= read -r LINK; do
    [[ -z "$LINK" ]] && continue
    CURRENT="${INBOUND_COUNT[$LINK]:-0}"
    INBOUND_COUNT["$LINK"]=$((CURRENT + 1))
  done <<< "$INTERNAL_LINKS"
  
done <<< "$(echo "$URLS" | head -20)"

echo ""
echo "======================================"
echo "🏝️ ORPHAN PAGES (0 inbound internal links):"
for SLUG in "${!INBOUND_COUNT[@]}"; do
  if [[ "${INBOUND_COUNT[$SLUG]}" -eq 0 ]]; then
    echo "  ⚠️  $SLUG"
  fi
done

echo ""
echo "📊 THIN INTERNAL LINKING (< 3 inbound):"
for SLUG in "${!INBOUND_COUNT[@]}"; do
  COUNT="${INBOUND_COUNT[$SLUG]}"
  if [[ "$COUNT" -gt 0 && "$COUNT" -lt 3 ]]; then
    echo "  ⚡ $SLUG ($COUNT inbound links)"
  fi
done
