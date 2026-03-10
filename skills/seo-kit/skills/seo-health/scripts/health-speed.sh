#!/usr/bin/env bash
# health-speed.sh — PageSpeed Insights + Core Web Vitals check
set -e

URL="${1:?Usage: health-speed.sh <url> [--mobile|--desktop|--both]}"
STRATEGY="${2:---both}"
API_KEY="${PAGESPEED_API_KEY:-}"

check_speed() {
  local url="$1" strategy="$2"
  local api_url="https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url=${url}&strategy=${strategy}&category=performance&category=seo&category=accessibility"
  [[ -n "$API_KEY" ]] && api_url="${api_url}&key=${API_KEY}"
  
  echo "📱 Checking ${strategy}..."
  local response
  response=$(curl -s -A "Mozilla/5.0 (compatible; SEOKit/1.0)" "$api_url")
  
  # Core Web Vitals from field data
  local lcp inp cls
  lcp=$(echo "$response" | jq -r '.loadingExperience.metrics.LARGEST_CONTENTFUL_PAINT_MS.percentile // "n/a"')
  inp=$(echo "$response" | jq -r '.loadingExperience.metrics.INTERACTION_TO_NEXT_PAINT.percentile // "n/a"')
  cls=$(echo "$response" | jq -r '.loadingExperience.metrics.CUMULATIVE_LAYOUT_SHIFT_SCORE.percentile // "n/a"')
  
  # Lab data
  local perf_score fcp speed_index ttfb
  perf_score=$(echo "$response" | jq -r '(.lighthouseResult.categories.performance.score // 0) * 100 | floor')
  fcp=$(echo "$response" | jq -r '.lighthouseResult.audits["first-contentful-paint"].numericValue // "n/a"')
  speed_index=$(echo "$response" | jq -r '.lighthouseResult.audits["speed-index"].numericValue // "n/a"')
  ttfb=$(echo "$response" | jq -r '.lighthouseResult.audits["server-response-time"].numericValue // "n/a"')
  
  # SEO score
  local seo_score
  seo_score=$(echo "$response" | jq -r '(.lighthouseResult.categories.seo.score // 0) * 100 | floor')
  
  echo ""
  echo "  Performance Score: ${perf_score}/100"
  echo "  SEO Score: ${seo_score}/100"
  echo ""
  echo "  Core Web Vitals (field data):"
  
  # LCP check
  if [[ "$lcp" != "n/a" ]]; then
    local lcp_s=$(echo "scale=2; $lcp / 1000" | bc 2>/dev/null || echo "$lcp")
    local lcp_status="✅ GOOD"
    [[ "$lcp" -gt 2500 && "$lcp" -le 4000 ]] && lcp_status="⚠️ NEEDS WORK"
    [[ "$lcp" -gt 4000 ]] && lcp_status="❌ POOR"
    echo "    LCP: ${lcp_s}s ${lcp_status} (target < 2.5s)"
  else
    echo "    LCP: No field data (not enough traffic)"
  fi
  
  # INP check
  if [[ "$inp" != "n/a" ]]; then
    local inp_status="✅ GOOD"
    [[ "$inp" -gt 200 && "$inp" -le 500 ]] && inp_status="⚠️ NEEDS WORK"
    [[ "$inp" -gt 500 ]] && inp_status="❌ POOR"
    echo "    INP: ${inp}ms ${inp_status} (target < 200ms)"
  else
    echo "    INP: No field data"
  fi
  
  # CLS check  
  if [[ "$cls" != "n/a" ]]; then
    local cls_fmt=$(echo "scale=2; $cls / 100" | bc 2>/dev/null || echo "$cls")
    local cls_status="✅ GOOD"
    [[ "$cls" -gt 10 && "$cls" -le 25 ]] && cls_status="⚠️ NEEDS WORK"
    [[ "$cls" -gt 25 ]] && cls_status="❌ POOR"
    echo "    CLS: ${cls_fmt} ${cls_status} (target < 0.1)"
  else
    echo "    CLS: No field data"
  fi
  
  echo ""
  echo "  Lab data:"
  [[ "$fcp" != "n/a" ]] && echo "    FCP: $(echo "scale=2; $fcp / 1000" | bc 2>/dev/null || echo "$fcp")s"
  [[ "$speed_index" != "n/a" ]] && echo "    Speed Index: $(echo "scale=2; $speed_index / 1000" | bc 2>/dev/null || echo "$speed_index")s"
  [[ "$ttfb" != "n/a" ]] && echo "    TTFB: $(echo "scale=0; $ttfb" | bc 2>/dev/null || echo "$ttfb")ms"
  
  # Top opportunities
  echo ""
  echo "  Top opportunities:"
  echo "$response" | jq -r '
    [.lighthouseResult.audits | to_entries[] | 
     select(.value.details.overallSavingsMs? > 0) |
     {name: .value.title, savings: .value.details.overallSavingsMs}] |
    sort_by(-.savings) | .[0:5][] |
    "    → \(.name) (save ~\(.savings)ms)"
  ' 2>/dev/null || echo "    (none detected)"
  
  # Save snapshot
  mkdir -p workspace/seo/health 2>/dev/null || true
  echo "$response" | jq '{
    date: now | strftime("%Y-%m-%d"),
    strategy: "'"$strategy"'",
    url: "'"$url"'",
    performance: (.lighthouseResult.categories.performance.score // 0),
    seo: (.lighthouseResult.categories.seo.score // 0),
    lcp: (.loadingExperience.metrics.LARGEST_CONTENTFUL_PAINT_MS.percentile // null),
    inp: (.loadingExperience.metrics.INTERACTION_TO_NEXT_PAINT.percentile // null),
    cls: (.loadingExperience.metrics.CUMULATIVE_LAYOUT_SHIFT_SCORE.percentile // null)
  }' > "workspace/seo/health/speed-$(date +%Y-%m-%d)-${strategy}.json" 2>/dev/null || true
}

echo "🏥 PageSpeed + Core Web Vitals Check"
echo "URL: $URL"
echo "======================================"

case "$STRATEGY" in
  --mobile)  check_speed "$URL" "mobile" ;;
  --desktop) check_speed "$URL" "desktop" ;;
  --both|*)  check_speed "$URL" "mobile"; echo ""; check_speed "$URL" "desktop" ;;
esac

echo ""
echo "======================================"
echo "Done. Snapshots saved to workspace/seo/health/"
