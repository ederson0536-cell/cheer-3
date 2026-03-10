#!/usr/bin/env bash
# seo-images/scripts/generate.sh
# Generate SEO images via Replicate's Nano Banana 2 API
#
# Usage:
#   ./generate.sh --style dark_data --headline '"$200M Revenue"' --ratio 16:9 --output ./hero.png
#   ./generate.sh --style founder_editorial --preset rooftop_golden --ratio 4:5 --output ./portrait.png
#   ./generate.sh --prompt "your custom prompt" --ratio 16:9 --output ./custom.png
#
# Requires: REPLICATE_API_TOKEN environment variable
# Model: google/nano-banana-2 on Replicate

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
STYLES_DIR="$SKILL_DIR/styles"

# Defaults
STYLE=""
PRESET=""
PROMPT=""
HEADLINE=""
SUBTEXT=""
CONTEXT=""
RATIO="16:9"
RESOLUTION="2K"
FORMAT="png"
OUTPUT=""
REFERENCE=""
GOOGLE_SEARCH="false"
IMAGE_SEARCH="false"
VARIATIONS=1

usage() {
  cat <<EOF
seo-images generator — Nano Banana 2 via Replicate

USAGE:
  $(basename "$0") [OPTIONS]

OPTIONS:
  --style NAME          Style template (founder_editorial, dark_data, product_lifestyle, social_card, warm_lifestyle, cinematic_scene)
  --preset NAME         Preset within the style (e.g. rooftop_golden, revenue_card)
  --prompt TEXT          Custom prompt (overrides style/preset)
  --headline TEXT        Headline text for rendering (social_card, dark_data)
  --subtext TEXT         Subtitle text
  --context TEXT         Article context for prompt building
  --ratio RATIO         Aspect ratio (1:1, 16:9, 4:5, 9:16, 3:2, 2:3, 21:9) [default: 16:9]
  --resolution RES      Resolution (0.5K, 1K, 2K, 4K) [default: 2K]
  --format FMT          Output format (jpg, png) [default: png]
  --output PATH         Output file path [default: ./seo-image-{timestamp}.png]
  --reference URL       Reference image URL for style consistency
  --search              Enable Google Search grounding for real-time data
  --image-search        Enable Google Image Search for visual context
  --variations N        Number of variations to generate [default: 1]
  --list-styles         List available styles and presets
  --dry-run             Show the prompt without calling the API

EXAMPLES:
  # Dark dashboard card with revenue stat
  $(basename "$0") --style dark_data --preset revenue_card --headline '"\$200M/Year"' --subtext '"Ridge Wallet · 4-Voice System"' --output ridge-hero.png

  # Founder portrait with golden hour preset
  $(basename "$0") --style founder_editorial --preset rooftop_golden --context "Newsletter author headshot" --ratio 4:5 --output author.png

  # Social share card
  $(basename "$0") --style social_card --preset dark_bold --headline '"The Agent That Never Sleeps"' --subtext '"How AI Replaced Ads Manager"' --output og-image.png

  # Custom prompt (bypass styles)
  $(basename "$0") --prompt "A hyper-realistic photo of..." --ratio 16:9 --output custom.png
EOF
  exit 0
}

list_styles() {
  echo "Available styles:"
  echo ""
  for f in "$STYLES_DIR"/*.json; do
    local name
    name=$(basename "$f" .json)
    # Skip non-style files (verticals, etc.)
    local has_presets
    has_presets=$(jq -r '.presets // empty' "$f" 2>/dev/null)
    [[ -z "$has_presets" || "$has_presets" == "null" ]] && continue

    local desc
    desc=$(jq -r '.description // ""' "$f" 2>/dev/null)
    local presets
    presets=$(jq -r '.presets | keys | join(", ")' "$f" 2>/dev/null || echo "none")
    echo "  $name"
    echo "    $desc"
    echo "    Presets: $presets"
    echo ""
  done
  exit 0
}

# Parse arguments
DRY_RUN=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --style) STYLE="$2"; shift 2 ;;
    --preset) PRESET="$2"; shift 2 ;;
    --prompt) PROMPT="$2"; shift 2 ;;
    --headline) HEADLINE="$2"; shift 2 ;;
    --subtext) SUBTEXT="$2"; shift 2 ;;
    --context) CONTEXT="$2"; shift 2 ;;
    --ratio) RATIO="$2"; shift 2 ;;
    --resolution) RESOLUTION="$2"; shift 2 ;;
    --format) FORMAT="$2"; shift 2 ;;
    --output) OUTPUT="$2"; shift 2 ;;
    --reference) REFERENCE="$2"; shift 2 ;;
    --search) GOOGLE_SEARCH="true"; shift ;;
    --image-search) IMAGE_SEARCH="true"; shift ;;
    --variations) VARIATIONS="$2"; shift 2 ;;
    --list-styles) list_styles ;;
    --dry-run) DRY_RUN=true; shift ;;
    --help|-h) usage ;;
    *) echo "Unknown option: $1"; usage ;;
  esac
done

# Validate
if [[ -z "$PROMPT" && -z "$STYLE" ]]; then
  echo "ERROR: Either --style or --prompt is required"
  usage
fi

# Set default output path
if [[ -z "$OUTPUT" ]]; then
  OUTPUT="./seo-image-$(date +%Y%m%d-%H%M%S).${FORMAT}"
fi

# Build prompt from style + preset if no custom prompt
if [[ -z "$PROMPT" ]]; then
  STYLE_FILE="$STYLES_DIR/${STYLE}.json"
  if [[ ! -f "$STYLE_FILE" ]]; then
    echo "ERROR: Style '$STYLE' not found. Available styles:"
    ls "$STYLES_DIR"/*.json 2>/dev/null | xargs -I{} basename {} .json | sed 's/^/  /'
    exit 1
  fi

  # Extract base prompt
  BASE_PROMPT=$(jq -r '.base_prompt' "$STYLE_FILE")

  # If preset specified, merge preset data
  if [[ -n "$PRESET" ]]; then
    PRESET_EXISTS=$(jq -r ".presets.${PRESET} // empty" "$STYLE_FILE")
    if [[ -z "$PRESET_EXISTS" ]]; then
      echo "ERROR: Preset '$PRESET' not found in style '$STYLE'. Available presets:"
      jq -r '.presets | keys[]' "$STYLE_FILE" | sed 's/^/  /'
      exit 1
    fi
    PRESET_DESC=$(jq -r ".presets.${PRESET}.description // \"\"" "$STYLE_FILE")
    echo "Using style: $STYLE / preset: $PRESET"
    echo "  $PRESET_DESC"
  fi

  # Get negative prompts
  NEGATIVES=$(jq -r '.schema.negative_prompt // .negative_prompt // [] | join(". ")' "$STYLE_FILE")

  # Build the prompt from preset data, replacing base_prompt placeholders
  # The base_prompt has {var} placeholders — we extract preset values and substitute
  PROMPT="$BASE_PROMPT"

  if [[ -n "$PRESET" ]]; then
    # Extract all useful fields from preset for substitution
    CAMERA=$(jq -r ".presets.${PRESET}.camera.camera_model // \"\"" "$STYLE_FILE")
    APERTURE=$(jq -r ".presets.${PRESET}.camera.aperture // \"\"" "$STYLE_FILE")
    LENS=$(jq -r ".presets.${PRESET}.camera.lens // \"\"" "$STYLE_FILE")
    SHOT_TYPE=$(jq -r ".presets.${PRESET}.camera.shot_type // \"\"" "$STYLE_FILE")
    FILM_STOCK=$(jq -r ".presets.${PRESET}.camera.film_stock // \"\"" "$STYLE_FILE")
    KEY_LIGHT=$(jq -r ".presets.${PRESET}.lighting.key_light // .presets.${PRESET}.lighting.source // \"\"" "$STYLE_FILE")
    FILL_LIGHT=$(jq -r ".presets.${PRESET}.lighting.fill_light // \"\"" "$STYLE_FILE")
    COLOR_TEMP=$(jq -r ".presets.${PRESET}.lighting.color_temperature // \"\"" "$STYLE_FILE")
    GRADE=$(jq -r ".presets.${PRESET}.color_and_style.grade // \"\"" "$STYLE_FILE")
    OVERALL_STYLE=$(jq -r ".presets.${PRESET}.color_and_style.overall_style // \"\"" "$STYLE_FILE")
    PALETTE=$(jq -r ".presets.${PRESET}.color_and_style.palette // [] | join(\", \")" "$STYLE_FILE")
    DIRECTOR=$(jq -r ".presets.${PRESET}.color_and_style.director_reference // \"\"" "$STYLE_FILE")
    ENVIRONMENT=$(jq -r ".presets.${PRESET}.environment // .presets.${PRESET}.scene // {} | to_entries | map(.value | if type == \"array\" then join(\", \") elif type == \"object\" then to_entries | map(.value | tostring) | join(\", \") else tostring end) | join(\". \")" "$STYLE_FILE" 2>/dev/null || echo "")
    BG_DESC=$(jq -r ".presets.${PRESET}.background.description // \"\"" "$STYLE_FILE")

    # Substitute known placeholders in base_prompt
    [[ -n "$CAMERA" && "$CAMERA" != "null" ]] && PROMPT="${PROMPT//\{camera_model\}/$CAMERA}" && PROMPT="${PROMPT//\{camera\}/$CAMERA}"
    [[ -n "$ENVIRONMENT" && "$ENVIRONMENT" != "null" ]] && PROMPT="${PROMPT//\{environment_description\}/$ENVIRONMENT}" && PROMPT="${PROMPT//\{scene_description\}/$ENVIRONMENT}"
    [[ -n "$KEY_LIGHT" && "$KEY_LIGHT" != "null" ]] && PROMPT="${PROMPT//\{lighting_description\}/$KEY_LIGHT}"
    [[ -n "$BG_DESC" && "$BG_DESC" != "null" ]] && PROMPT="${PROMPT//\{background_description\}/$BG_DESC}"
    [[ -n "$DIRECTOR" && "$DIRECTOR" != "null" ]] && PROMPT="${PROMPT//\{director_reference\}/$DIRECTOR}"

    # Extract content description for data cards (dark_data style)
    CONTENT_DESC=$(jq -r ".presets.${PRESET}.description // \"\"" "$STYLE_FILE")
    [[ -n "$CONTENT_DESC" && "$CONTENT_DESC" != "null" ]] && PROMPT="${PROMPT//\{content_description\}/$CONTENT_DESC}"

    # Extract color mood from palette/grade
    COLOR_MOOD="${GRADE:-premium dark aesthetic}"
    PROMPT="${PROMPT//\{color_mood\}/$COLOR_MOOD}"

    # Substitute subtitle/headline placeholders
    [[ -n "$HEADLINE" ]] && PROMPT="${PROMPT//\{headline\}/$HEADLINE}"
    PROMPT="${PROMPT//\{headline_font\}/bold white Impact}" # sensible default
    PROMPT="${PROMPT//\{subtitle_treatment\}/clean subtitle below}"
    PROMPT="${PROMPT//\{layout_description\}/centered composition}"
    PROMPT="${PROMPT//\{mood\}/cinematic and aspirational}"
    PROMPT="${PROMPT//\{subject_description\}/a person}"

    # Strip any remaining {placeholders} and clean up dangling prepositions/punctuation
    PROMPT=$(echo "$PROMPT" | sed 's/{[a-z_]*}//g')
    # Clean: "of in ," → remove dangling prepositions before commas
    PROMPT=$(echo "$PROMPT" | sed 's/ of in / /g; s/ in , / /g; s/ of , / /g; s/ on , / /g')
    # Clean: multiple spaces, double commas, leading/trailing punctuation
    PROMPT=$(echo "$PROMPT" | sed 's/  */ /g; s/,  *,/,/g; s/^[, ]*//' | sed 's/[, ]*$//')

    # Append rich detail from preset
    PARTS=""
    [[ -n "$CAMERA" && "$CAMERA" != "null" ]] && PARTS="$PARTS Shot on $CAMERA"
    [[ -n "$APERTURE" && "$APERTURE" != "null" ]] && PARTS="$PARTS at $APERTURE."
    [[ -n "$LENS" && "$LENS" != "null" ]] && PARTS="$PARTS Lens: $LENS."
    [[ -n "$SHOT_TYPE" && "$SHOT_TYPE" != "null" ]] && PARTS="$PARTS $SHOT_TYPE framing."
    [[ -n "$KEY_LIGHT" && "$KEY_LIGHT" != "null" ]] && PARTS="$PARTS Lighting: $KEY_LIGHT."
    [[ -n "$FILL_LIGHT" && "$FILL_LIGHT" != "null" ]] && PARTS="$PARTS Fill: $FILL_LIGHT."
    [[ -n "$GRADE" && "$GRADE" != "null" ]] && PARTS="$PARTS Color grade: $GRADE."
    [[ -n "$FILM_STOCK" && "$FILM_STOCK" != "null" ]] && PARTS="$PARTS Film stock: $FILM_STOCK."
    [[ -n "$OVERALL_STYLE" && "$OVERALL_STYLE" != "null" ]] && PARTS="$PARTS Style reference: $OVERALL_STYLE."
    [[ -n "$DIRECTOR" && "$DIRECTOR" != "null" ]] && PARTS="$PARTS Directed by $DIRECTOR."
    [[ -n "$PARTS" ]] && PROMPT="$PROMPT.$PARTS"
  else
    # No preset — substitute what we can from user input, strip the rest
    [[ -n "$HEADLINE" ]] && PROMPT="${PROMPT//\{headline\}/$HEADLINE}"
    PROMPT="${PROMPT//\{headline_font\}/bold white Impact}"
    PROMPT="${PROMPT//\{subtitle_treatment\}/clean subtitle below}"
    PROMPT="${PROMPT//\{layout_description\}/centered composition}"
    PROMPT="${PROMPT//\{mood\}/cinematic and aspirational}"
    PROMPT="${PROMPT//\{subject_description\}/a person}"
    PROMPT="${PROMPT//\{background_description\}/dark background}"
    # Strip any remaining unfilled placeholders and clean up punctuation
    PROMPT=$(echo "$PROMPT" | sed 's/{[a-z_]*}//g' | sed 's/  */ /g' | sed 's/,  *,/,/g' | sed 's/^[, ]*//' | sed 's/[, ]*$//')
  fi

  # Append headline/subtext if provided
  if [[ -n "$HEADLINE" ]]; then
    PROMPT="$PROMPT. Large rendered text reading $HEADLINE."
  fi
  if [[ -n "$SUBTEXT" ]]; then
    PROMPT="$PROMPT Below that, smaller text reading $SUBTEXT."
  fi
  if [[ -n "$CONTEXT" ]]; then
    PROMPT="$PROMPT Context: $CONTEXT."
  fi

  # Append negative prompt
  if [[ -n "$NEGATIVES" ]]; then
    PROMPT="$PROMPT. Avoid: $NEGATIVES"
  fi
fi

echo ""
echo "━━━ Prompt ━━━"
echo "$PROMPT"
echo ""
echo "Settings: ratio=$RATIO resolution=$RESOLUTION format=$FORMAT"
echo ""

if $DRY_RUN; then
  echo "[DRY RUN] Would generate with the above prompt."
  exit 0
fi

# Check API token (only needed for actual generation)
if [[ -z "${REPLICATE_API_TOKEN:-}" ]]; then
  echo "ERROR: REPLICATE_API_TOKEN not set"
  echo "Get your token at https://replicate.com/account/api-tokens"
  exit 1
fi

# Build image_input array
IMAGE_INPUT="[]"
if [[ -n "$REFERENCE" ]]; then
  IMAGE_INPUT="[\"$REFERENCE\"]"
fi

# Ensure output directory exists
mkdir -p "$(dirname "$OUTPUT")"

# Call Replicate API
echo "Generating via Replicate (google/nano-banana-2)..."

for i in $(seq 1 "$VARIATIONS"); do
  RESPONSE=$(curl -s -X POST "https://api.replicate.com/v1/models/google/nano-banana-2/predictions" \
    -H "Authorization: Bearer $REPLICATE_API_TOKEN" \
    -H "Content-Type: application/json" \
    -H "Prefer: wait" \
    -d "$(jq -n \
      --arg prompt "$PROMPT" \
      --arg ratio "$RATIO" \
      --arg resolution "$RESOLUTION" \
      --arg format "$FORMAT" \
      --argjson search "$GOOGLE_SEARCH" \
      --argjson img_search "$IMAGE_SEARCH" \
      --argjson image_input "$IMAGE_INPUT" \
      '{
        input: {
          prompt: $prompt,
          aspect_ratio: $ratio,
          resolution: $resolution,
          output_format: $format,
          google_search: $search,
          image_search: $img_search,
          image_input: $image_input
        }
      }')")

  STATUS=$(echo "$RESPONSE" | jq -r '.status // "unknown"')
  PRED_ID=$(echo "$RESPONSE" | jq -r '.id // "unknown"')

  if [[ "$STATUS" == "succeeded" ]]; then
    IMAGE_URL=$(echo "$RESPONSE" | jq -r '.output[0] // .output // empty')
    if [[ -n "$IMAGE_URL" ]]; then
      # Determine output filename for variations
      if [[ "$VARIATIONS" -gt 1 ]]; then
        EXT="${OUTPUT##*.}"
        BASE="${OUTPUT%.*}"
        OUT_FILE="${BASE}-v${i}.${EXT}"
      else
        OUT_FILE="$OUTPUT"
      fi
      curl -s -o "$OUT_FILE" "$IMAGE_URL"
      echo "✅ Saved: $OUT_FILE"
    else
      echo "⚠️  No image URL in response"
      echo "$RESPONSE" | jq .
    fi
  elif [[ "$STATUS" == "processing" || "$STATUS" == "starting" ]]; then
    echo "⏳ Prediction $PRED_ID still processing. Polling..."
    for attempt in $(seq 1 30); do
      sleep 3
      POLL=$(curl -s -H "Authorization: Bearer $REPLICATE_API_TOKEN" \
        "https://api.replicate.com/v1/predictions/$PRED_ID")
      POLL_STATUS=$(echo "$POLL" | jq -r '.status')

      if [[ "$POLL_STATUS" == "succeeded" ]]; then
        IMAGE_URL=$(echo "$POLL" | jq -r '.output[0] // .output // empty')
        if [[ "$VARIATIONS" -gt 1 ]]; then
          EXT="${OUTPUT##*.}"
          BASE="${OUTPUT%.*}"
          OUT_FILE="${BASE}-v${i}.${EXT}"
        else
          OUT_FILE="$OUTPUT"
        fi
        curl -s -o "$OUT_FILE" "$IMAGE_URL"
        echo "✅ Saved: $OUT_FILE"
        break
      elif [[ "$POLL_STATUS" == "failed" || "$POLL_STATUS" == "canceled" ]]; then
        echo "❌ Generation failed: $(echo "$POLL" | jq -r '.error // "unknown"')"
        break
      fi
      echo "  ... still processing (attempt $attempt/30)"
    done
    if [[ "$attempt" -ge 30 ]]; then
      echo "❌ Timed out after 90 seconds. Prediction ID: $PRED_ID"
      echo "   Check status: curl -H 'Authorization: Bearer \$REPLICATE_API_TOKEN' https://api.replicate.com/v1/predictions/$PRED_ID"
    fi
  else
    echo "❌ Error: $STATUS"
    echo "$RESPONSE" | jq -r '.error // .' 2>/dev/null || echo "$RESPONSE"
  fi
done

echo ""
echo "Done."
