#!/usr/bin/env bash
# health-crawl.sh — Crawl health audit
set +o pipefail
set -e

DOMAIN="${1:?Usage: health-crawl.sh <domain> [--sitemap URL] [--limit 50]}"
SITEMAP="https://${DOMAIN}/sitemap.xml"
LIMIT=50

while [[ $# -gt 1 ]]; do
  case "$2" in
    --sitemap) SITEMAP="$3"; shift 2 ;;
    --limit) LIMIT="$3"; shift 2 ;;
    *) shift ;;
  esac
done

echo "🕷️ Crawl Health Audit: $DOMAIN"
echo "Sitemap: $SITEMAP"
echo "======================================"

# Check robots.txt
echo ""
echo "📋 robots.txt"
ROBOTS=$(curl -s -A "Mozilla/5.0 (compatible; SEOKit/1.0)"I "https://${DOMAIN}/robots.txt" -o /dev/null -w "%{http_code}")
if [[ "$ROBOTS" == "200" ]]; then
  echo "  ✅ robots.txt exists"
  SITEMAP_IN_ROBOTS=$(curl -s -A "Mozilla/5.0 (compatible; SEOKit/1.0)" "https://${DOMAIN}/robots.txt" | grep -i "sitemap" || true)
  if [[ -n "$SITEMAP_IN_ROBOTS" ]]; then
    echo "  ✅ Sitemap referenced in robots.txt"
  else
    echo "  ⚠️ No sitemap reference in robots.txt"
  fi
else
  echo "  ❌ robots.txt not found ($ROBOTS)"
fi

# Check sitemap
echo ""
echo "🗺️ Sitemap"
SITEMAP_STATUS=$(curl -s -A "Mozilla/5.0 (compatible; SEOKit/1.0)"I "$SITEMAP" -o /dev/null -w "%{http_code}")
if [[ "$SITEMAP_STATUS" == "200" ]]; then
  URLS=$(curl -s -A "Mozilla/5.0 (compatible; SEOKit/1.0)"L "$SITEMAP" | grep -oP '<loc>\K[^<]+' | head -"$LIMIT")
  URL_COUNT=$(wc -l <<< "$URLS")
  echo "  ✅ Sitemap accessible ($URL_COUNT URLs, checking top $LIMIT)"
else
  echo "  ❌ Sitemap not accessible ($SITEMAP_STATUS)"
  echo "  Trying sitemap_index..."
  URLS=$(curl -s -A "Mozilla/5.0 (compatible; SEOKit/1.0)"L "$SITEMAP" | grep -oP '<loc>\K[^<]+' | head -3 | while read -r SUB; do
    curl -s -A "Mozilla/5.0 (compatible; SEOKit/1.0)"L "$SUB" 2>/dev/null | grep -oP '<loc>\K[^<]+' | head -20
  done)
  URL_COUNT=$(wc -l <<< "$URLS")
  echo "  Found $URL_COUNT URLs from sitemap index"
fi

[[ -z "$URLS" ]] && { echo "No URLs found. Exiting."; exit 1; }

# Crawl pages
BROKEN=0
MISSING_TITLE=0
MISSING_DESC=0
MISSING_CANONICAL=0
REDIRECT_CHAINS=0
MIXED_CONTENT=0

echo ""
echo "🔍 Checking pages..."

while IFS= read -r PAGE; do
  [[ -z "$PAGE" ]] && continue
  
  # Get page
  RESPONSE=$(curl -s -A "Mozilla/5.0 (compatible; SEOKit/1.0)"L --max-time 10 -w "\n%{http_code}" "$PAGE" 2>/dev/null)
  STATUS=$(echo "$RESPONSE" | tail -1)
  BODY=$(echo "$RESPONSE" | sed '$d')
  
  SLUG=$(echo "$PAGE" | sed "s|https://${DOMAIN}||")
  
  if [[ "$STATUS" != "200" ]]; then
    echo "  ❌ $SLUG → HTTP $STATUS"
    BROKEN=$((BROKEN + 1))
    continue
  fi
  
  # Check meta tags
  TITLE=$(echo "$BODY" | grep -oP '<title>\K[^<]*' | head -1)
  DESC=$(echo "$BODY" | grep -oP 'name="description"[^>]*content="\K[^"]*' | head -1)
  CANONICAL=$(echo "$BODY" | grep -oP 'rel="canonical"[^>]*href="\K[^"]*' | head -1)
  
  ISSUES=""
  [[ -z "$TITLE" ]] && { ISSUES="${ISSUES} no-title"; MISSING_TITLE=$((MISSING_TITLE + 1)); }
  [[ -z "$DESC" ]] && { ISSUES="${ISSUES} no-description"; MISSING_DESC=$((MISSING_DESC + 1)); }
  [[ -z "$CANONICAL" ]] && { ISSUES="${ISSUES} no-canonical"; MISSING_CANONICAL=$((MISSING_CANONICAL + 1)); }
  
  # Check for mixed content
  MIXED=$(echo "$BODY" | grep -c 'src="http://' 2>/dev/null || true)
  [[ "$MIXED" -gt 0 ]] && { ISSUES="${ISSUES} mixed-content"; MIXED_CONTENT=$((MIXED_CONTENT + 1)); }
  
  if [[ -n "$ISSUES" ]]; then
    echo "  ⚠️ $SLUG:$ISSUES"
  fi
  
done <<< "$(echo "$URLS" | head -"$LIMIT")"

echo ""
echo "======================================"
echo "📊 Summary:"
echo "  Pages checked: $LIMIT"
echo "  Broken pages (non-200): $BROKEN"
echo "  Missing title: $MISSING_TITLE"
echo "  Missing meta description: $MISSING_DESC"
echo "  Missing canonical: $MISSING_CANONICAL"
echo "  Mixed content: $MIXED_CONTENT"

TOTAL_ISSUES=$((BROKEN + MISSING_TITLE + MISSING_DESC + MISSING_CANONICAL + MIXED_CONTENT))
if [[ "$TOTAL_ISSUES" -eq 0 ]]; then
  echo ""
  echo "  ✅ No issues found!"
else
  echo ""
  echo "  ⚠️ $TOTAL_ISSUES total issues found"
fi

# Save snapshot
mkdir -p workspace/seo/health 2>/dev/null || true
echo "{\"date\":\"$(date +%Y-%m-%d)\",\"domain\":\"${DOMAIN}\",\"broken\":${BROKEN},\"missing_title\":${MISSING_TITLE},\"missing_desc\":${MISSING_DESC},\"missing_canonical\":${MISSING_CANONICAL},\"mixed_content\":${MIXED_CONTENT}}" > "workspace/seo/health/crawl-$(date +%Y-%m-%d).json" 2>/dev/null || true
