#!/usr/bin/env bash
# health-images.sh — Image optimization audit
set -e

DOMAIN="${1:?Usage: health-images.sh <domain> [--pages 10]}"
PAGES="${3:-10}"

echo "🖼️ Image Optimization Audit: $DOMAIN"
echo "======================================"

# Get top pages from sitemap
SITEMAP="https://${DOMAIN}/sitemap.xml"
URLS=$(curl -s -A "Mozilla/5.0 (compatible; SEOKit/1.0)"L "$SITEMAP" 2>/dev/null | grep -oP '<loc>\K[^<]+' | head -"$PAGES")

[[ -z "$URLS" ]] && { echo "No sitemap found. Checking homepage only."; URLS="https://${DOMAIN}"; }

TOTAL_IMAGES=0
MISSING_ALT=0
OVERSIZED=0
WRONG_FORMAT=0
MISSING_DIMENSIONS=0
MISSING_LAZY=0

while IFS= read -r PAGE; do
  [[ -z "$PAGE" ]] && continue
  SLUG=$(echo "$PAGE" | sed "s|https://${DOMAIN}||")
  [[ -z "$SLUG" ]] && SLUG="/"
  
  BODY=$(curl -s -A "Mozilla/5.0 (compatible; SEOKit/1.0)"L --max-time 10 "$PAGE" 2>/dev/null)
  
  # Find all images
  IMAGES=$(echo "$BODY" | grep -oP '<img[^>]+>' | head -20)
  IMG_COUNT=$(echo "$IMAGES" | grep -c '<img' 2>/dev/null || echo 0)
  
  PAGE_MISSING_ALT=0
  PAGE_MISSING_DIM=0
  
  while IFS= read -r IMG; do
    [[ -z "$IMG" ]] && continue
    TOTAL_IMAGES=$((TOTAL_IMAGES + 1))
    
    # Check alt text
    ALT=$(echo "$IMG" | grep -oP 'alt="\K[^"]*' || true)
    if [[ -z "$ALT" || "$ALT" == " " ]]; then
      PAGE_MISSING_ALT=$((PAGE_MISSING_ALT + 1))
      MISSING_ALT=$((MISSING_ALT + 1))
    fi
    
    # Check dimensions
    WIDTH=$(echo "$IMG" | grep -oP 'width="\K[^"]*' || true)
    HEIGHT=$(echo "$IMG" | grep -oP 'height="\K[^"]*' || true)
    if [[ -z "$WIDTH" || -z "$HEIGHT" ]]; then
      MISSING_DIMENSIONS=$((MISSING_DIMENSIONS + 1))
    fi
    
    # Check format
    SRC=$(echo "$IMG" | grep -oP 'src="\K[^"]*' || true)
    if echo "$SRC" | grep -qiE '\.(png|bmp|tiff)(\?|$)'; then
      WRONG_FORMAT=$((WRONG_FORMAT + 1))
    fi
    
    # Check lazy loading
    if ! echo "$IMG" | grep -q 'loading="lazy"'; then
      MISSING_LAZY=$((MISSING_LAZY + 1))
    fi
    
  done <<< "$IMAGES"
  
  if [[ "$PAGE_MISSING_ALT" -gt 0 ]]; then
    echo "  ⚠️ $SLUG: $IMG_COUNT images, $PAGE_MISSING_ALT missing alt text"
  else
    echo "  ✅ $SLUG: $IMG_COUNT images OK"
  fi
  
done <<< "$URLS"

echo ""
echo "======================================"
echo "📊 Summary:"
echo "  Total images checked: $TOTAL_IMAGES"
echo "  Missing alt text: $MISSING_ALT"
echo "  Missing dimensions (causes CLS): $MISSING_DIMENSIONS"  
echo "  Wrong format (should be WebP/AVIF): $WRONG_FORMAT"
echo "  Missing lazy loading: $MISSING_LAZY"

# Save snapshot
mkdir -p workspace/seo/health 2>/dev/null || true
echo "{\"date\":\"$(date +%Y-%m-%d)\",\"domain\":\"${DOMAIN}\",\"total\":${TOTAL_IMAGES},\"missing_alt\":${MISSING_ALT},\"missing_dimensions\":${MISSING_DIMENSIONS},\"wrong_format\":${WRONG_FORMAT},\"missing_lazy\":${MISSING_LAZY}}" > "workspace/seo/health/images-$(date +%Y-%m-%d).json" 2>/dev/null || true
