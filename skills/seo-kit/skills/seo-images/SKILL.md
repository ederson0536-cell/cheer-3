---
name: seo-images
version: "1.0"
description: "Generate premium SEO article images using Nano Banana 2. Six locked-in visual styles with cinema-grade JSON prompts. No stock photo slop."
argument-hint: '/seo-image "Ridge Wallet Revenue Breakdown" --style dark_data --ratio 16:9'
allowed-tools: Bash, Read, Write, WebFetch
user-invocable: true
metadata:
  tags:
    - image-generation
    - seo
    - content
    - nano-banana
  requires:
    env:
      - REPLICATE_API_TOKEN
    bins:
      - curl
      - jq
---

# SEO Images — Premium AI Image Generation for Content

Generate publication-quality images for blog posts, newsletters, and social media using structured JSON prompts and Nano Banana 2 (Gemini 3.1 Flash Image).

**No stock photo slop. No generic AI art. Images that match the quality of your writing.**

## Quick Start

```bash
# Generate a dark dashboard hero image
/seo-image "OpenClaw Meta Ads: $1,400/mo Saved" --style dark_data --ratio 16:9

# Generate a founder portrait
/seo-image "founder working late" --style founder_editorial --preset office_morning --ratio 4:5

# Generate a product shot
/seo-image "premium leather wallet on marble" --style product_lifestyle --ratio 1:1

# Generate a social share card
/seo-image "Ridge Wallet: $200M/Year" --style social_card --ratio 16:9
```

## Setup

### Option A: Replicate (recommended)

```bash
# Get your API token from https://replicate.com/account/api-tokens
export REPLICATE_API_TOKEN="r8_your_token_here"
```

**Model:** `google/nano-banana-2` on Replicate
**Cost:** ~$0.02-0.05 per image at 1K, ~$0.08-0.12 at 2K
**Speed:** 5-15 seconds per image

### Option B: Google AI Studio (free tier available)

```bash
# Get your API key from https://aistudio.google.com/apikey
export GOOGLE_AI_API_KEY="your_key_here"
```

**Model:** `gemini-3.1-flash-image-preview`
**Cost:** Free tier available (rate limited), then pay-as-you-go
**Endpoint:** `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-image-preview:generateContent`

### Option C: fal.ai

```bash
export FAL_KEY="your_key_here"
```

### Option D: Any provider with Nano Banana 2 access

The skill generates structured JSON prompts. The prompt is the valuable part — pipe it to whatever provider you prefer.

## How It Works

1. **You provide:** Article context + style selection + optional customization
2. **Skill builds:** A cinema-grade structured JSON prompt with full camera/lighting/color specs
3. **Skill flattens:** JSON into an optimized text prompt for the model
4. **Skill calls:** Replicate API (or your preferred provider)
5. **Skill outputs:** 1-3 variations at your specified aspect ratio and resolution

## The 6 Visual Styles

Read the full style definitions in `styles/`. Each style has:
- Full JSON schema with every parameter documented
- Presets for common use cases
- Negative prompts to avoid common AI failures
- Vertical targeting (which industries/content types it works for)

### 1. `founder_editorial` — Cinematic People Photography
Hyper-realistic editorial portraits. Real people in real environments. Magazine-quality lighting and composition. Shot on named cameras with specific lenses.

**Best for:** About pages, founder stories, team pages, interview headers, newsletter author images

**Presets:** `rooftop_golden`, `office_morning`, `street_candid`

### 2. `dark_data` — Premium Data Visualization Cards
Dark glass dashboard cards with bold stats, clean typography, and subtle depth. Rendered text that's actually legible. Think Bloomberg Terminal meets Stripe marketing.

**Best for:** Stats callouts, performance reports, case study headers, metric hero images, newsletter stats

**Presets:** `revenue_card`, `performance_card`

### 3. `product_lifestyle` — Editorial Product Photography
Premium product shots in lifestyle contexts. The product is hero but the environment tells a story. Phase One quality.

**Best for:** Product launches, comparison posts, e-commerce features, DTC content

### 4. `social_card` — Scroll-Stopping Typography
High-impact text-forward cards for blog OG images, tweet cards, LinkedIn headers. Bold type, high contrast, designed to stop the scroll at thumbnail size.

**Best for:** Blog share images, tweet cards, LinkedIn post images, newsletter hero, chapter headers

### 5. `warm_lifestyle` — Bright Editorial Spaces
Warm, aspirational lifestyle photography. Natural light, earth tones, beautiful spaces. Film-stock quality.

**Best for:** Wellness content, real estate, creator economy, coaching, course promos

### 6. `cinematic_scene` — Movie-Still Narratives
Film-quality scenes with dramatic lighting and deliberate composition. Named director references for specific visual languages.

**Best for:** Long-form editorial, investigative pieces, dramatic feature stories, newsletter covers

## Prompt Architecture

Every style uses this structured JSON format:

```json
{
  "prompt": "the flattened text prompt sent to the model",
  "style_id": "which style template was used",
  "subject": { ... },
  "environment": { ... },
  "camera": {
    "camera_model": "specific camera body (e.g. Leica M11)",
    "lens_focal_length_mm": 50,
    "aperture": "f/1.4",
    "shot_type": "medium_close_up",
    "perspective": "eye_level",
    "depth_of_field": "shallow"
  },
  "lighting": {
    "key_light": "direction, quality, falloff description",
    "fill_light": "source and intensity",
    "rim_light": "position and effect",
    "color_temperature": "warm | neutral | cool | mixed"
  },
  "color_and_style": {
    "palette": ["#hex1", "#hex2", "#hex3"],
    "grade": "specific color grading description",
    "grain": "film grain type and intensity",
    "overall_style": "cultural reference (e.g. 'A24 meets Acne Studios')"
  },
  "output_settings": {
    "aspect_ratio": "16:9",
    "resolution": {"width": 1920, "height": 1080},
    "format": "png"
  },
  "negative_prompt": ["array of specific things to avoid"]
}
```

**Why this matters:** Generic prompts produce generic images. Specifying the exact camera model, aperture, film stock, lighting rig, and color grade gives Nano Banana 2 the detail it needs to produce images that look like they were shot by a real photographer with real equipment.

## Generating Images

### Via the generation script

```bash
# Set your API token
export REPLICATE_API_TOKEN="your_token"

# Generate from a style + context
bash scripts/generate.sh \
  --style dark_data \
  --context "Article about Ridge Wallet scaling to \$200M revenue" \
  --headline "Ridge Wallet: \$200M/Year" \
  --subtext "4-Voice Content System · 500+ AI Creatives/Day" \
  --ratio 16:9 \
  --resolution 2K \
  --output ./output/ridge-hero.png

# Generate with a preset
bash scripts/generate.sh \
  --style founder_editorial \
  --preset office_morning \
  --context "Newsletter author headshot" \
  --ratio 4:5 \
  --output ./output/author.png

# Generate a social card
bash scripts/generate.sh \
  --style social_card \
  --headline "The Agent That Never Sleeps" \
  --subtext "How AI Replaced 90 Minutes of Ads Manager" \
  --ratio 16:9 \
  --output ./output/og-image.png
```

### Via the agent (OpenClaw / Claude Code / Codex)

The agent reads the article context, selects the appropriate style, builds the full JSON prompt, and calls the API. Example:

```
/seo-image for my article "OpenClaw Meta Ads Complete Guide" — I need a hero image and a social share card
```

The agent will:
1. Read the article to understand the content
2. Select `dark_data` for the hero (tech/data content)
3. Select `social_card` for the share image
4. Build full structured prompts for each
5. Generate via Replicate
6. Save both images to the specified output directory

## Reference Images

For style consistency across articles, maintain reference images:

```
references/
  founder_editorial/   → 3-5 gold-standard portrait references
  dark_data/           → 3-5 reference dashboard cards
  product_lifestyle/   → 3-5 reference product shots
  social_card/         → 3-5 reference typography cards
  warm_lifestyle/      → 3-5 reference lifestyle shots
  cinematic_scene/     → 3-5 reference film stills
```

Pass reference images to the API via `image_input` to maintain visual consistency:

```bash
curl -s -X POST "https://api.replicate.com/v1/models/google/nano-banana-2/predictions" \
  -H "Authorization: Bearer $REPLICATE_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "prompt": "your flattened prompt here",
      "image_input": ["https://url-to-reference-image.png"],
      "aspect_ratio": "16:9",
      "resolution": "2K",
      "output_format": "png"
    }
  }'
```

## API Reference

### Replicate — `google/nano-banana-2`

```bash
# Create prediction
curl -s -X POST "https://api.replicate.com/v1/models/google/nano-banana-2/predictions" \
  -H "Authorization: Bearer $REPLICATE_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "prompt": "string — the full text prompt",
      "image_input": ["array of image URLs — up to 14 reference images"],
      "aspect_ratio": "16:9",
      "resolution": "1K | 2K | 4K",
      "output_format": "jpg | png",
      "google_search": false,
      "image_search": false
    }
  }'

# Poll for result
curl -s -H "Authorization: Bearer $REPLICATE_API_TOKEN" \
  "https://api.replicate.com/v1/predictions/{prediction_id}"
```

**Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `prompt` | string | required | The image description |
| `image_input` | array of URLs | [] | Reference images (up to 14) |
| `aspect_ratio` | enum | match_input_image | 1:1, 3:2, 2:3, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9, 1:4, 4:1, 1:8, 8:1 |
| `resolution` | enum | 1K | 0.5K, 1K, 2K, 4K |
| `output_format` | enum | jpg | jpg, png |
| `google_search` | bool | false | Use real-time web data |
| `image_search` | bool | false | Use Google Image Search for visual context |

### Google AI Studio — `gemini-3.1-flash-image-preview`

```bash
curl -s -X POST \
  "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-image-preview:generateContent?key=$GOOGLE_AI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "contents": [{"parts": [{"text": "your prompt here"}]}],
    "generationConfig": {
      "responseModalities": ["TEXT", "IMAGE"],
      "imageSizeOptions": {"aspectRatio": "16:9"}
    }
  }'
```

## Prompt Flattening

The structured JSON is for YOUR reference and consistency. The model receives a flattened text version. The `scripts/generate.sh` script handles this automatically, but here's the logic:

```
JSON structured prompt → Flatten to narrative text → Send to model

Example:
{
  "subject": {"age": 32, "pose": "leaning on railing"},
  "camera": {"camera_model": "Leica M11", "aperture": "f/1.4"},
  "lighting": {"key_light": "warm sunset from camera-left"}
}

→ "hyper-realistic portrait of a 32-year-old man leaning casually on
   a railing, warm sunset light from camera-left with soft falloff,
   shot on Leica M11 at f/1.4, shallow depth of field..."
```

The structured format ensures consistency and makes it easy to tweak individual parameters without rewriting the entire prompt.

## Tips

1. **Camera specificity matters.** "Shot on Leica M11 at f/1.4" produces dramatically different results than "professional photography."
2. **Name the color grade.** "Cinematic teal and orange" or "desaturated Portra 400 emulation" gives the model a clear reference point.
3. **Negative prompts prevent common failures.** Always include "no warped hands" for people shots and "no illegible text" for typography.
4. **Reference images are your secret weapon.** Feed 1-3 reference images via `image_input` to maintain style consistency across a content series.
5. **Text rendering works now.** Use quotes around text you want rendered: `"GROWTH PLAYS"`. Specify the font: `"bold white Impact font"`. NB2 handles this well.
6. **Don't over-prompt.** If the prompt exceeds ~500 words, the model starts losing focus. Keep the flattened version tight. The JSON is for your records.
