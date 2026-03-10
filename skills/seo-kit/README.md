# SEO Kit for OpenClaw

An AI agent that finds keywords, writes content, builds backlinks, monitors rankings, and self-improves. Four skills that chain into a compounding loop.

**Built by [Matt Berman](https://x.com/TheMattBerman) / [Big Players](https://bigplayers.co)**

---

## What This Does

Most people know what to do for SEO. Nobody does it consistently.

This agent does:

1. **Discovers** keyword opportunities from your actual Google Search Console data
2. **Writes** psychology-driven content in your brand voice (not generic AI slop)
3. **Builds links** through competitor mining, unlinked mentions, and broken link outreach
4. **Monitors** rankings weekly and flags what's climbing or dropping
5. **Checks health** with PageSpeed audits, crawl checks, and image optimization
6. **Repeats** automatically, getting smarter about your brand every week

The loop is the point. Each cycle feeds the next one.

---

## The Four Skills

### skills/seo-agent — Discovery + Monitoring

The brain that finds opportunities and tracks progress.

| Script | What It Does |
|--------|-------------|
| `seo-discover.sh` | Finds strike zone keywords (positions 5-20) from GSC + DataForSEO |
| `seo-monitor.sh` | Weekly ranking snapshots, flags climbers and droppers |
| `seo-compete.sh` | Competitor gap analysis: keywords they rank for that you don't |

### skills/seo-forge — Content Engine

The writer that sounds like you, not like ChatGPT.

| Script | What It Does |
|--------|-------------|
| `seo-interview.sh` | 8 questions that build your brand voice and positioning |
| `seo-research.sh` | SERP analysis, People Also Ask, search intent classification |
| `seo-check.sh` | Validates your GSC and DataForSEO connections |

**What makes it different:** Interview mode learns your voice. Weekly refinement keeps it current. Psychology frameworks make content convert, not just rank. Anti-AI-Overview strategy bakes in real experience markers.

### skills/seo-links — Backlink Acquisition

Content without links is a prayer. This skill finds link opportunities.

| Script | What It Does |
|--------|-------------|
| `link-mine.sh` | Mines competitor backlink profiles for targets |
| `link-mentions.sh` | Finds unlinked brand mentions (easiest links to get) |
| `link-broken.sh` | Finds broken links on resource pages, pitches your content |
| `link-internal.sh` | Audits internal linking, finds orphan pages |
| `link-prospect.sh` | Finds "best tools" and resource pages to get listed on |

### skills/seo-images — AI Image Generation

Publication-quality images for your SEO content. No stock photos.

| Style | What It Produces |
|-------|-----------------|
| `founder_editorial` | Cinematic portraits — Leica M11, A24 aesthetic, magazine quality |
| `dark_data` | Dashboard stat cards — Bloomberg meets Stripe, bold metrics |
| `product_lifestyle` | Editorial product photography — Phase One quality |
| `social_card` | Typography-forward share cards — scroll-stopping at thumbnail |
| `warm_lifestyle` | Bright aspirational lifestyle — Portra 400 film stock |
| `cinematic_scene` | Movie-still narratives — ARRI Alexa, director references |

**21 presets** across 6 styles. **6 vertical routing maps** (SaaS, DTC, newsletter, agency, AI/tech, finance) that auto-select the right style for your content.

Integrates with SEO Forge — after writing an article, it offers to generate hero images, inline visuals, and social share cards matched to your content's vertical.

```bash
# Quick generate
bash skills/seo-images/scripts/generate.sh --style dark_data --preset revenue_card \
  --headline '"$200M/Year"' --ratio 16:9 --output hero.png

# Dry run (no API needed)
bash skills/seo-images/scripts/generate.sh --style cinematic_scene --preset late_night_office \
  --context "Founder building AI agents" --ratio 21:9 --dry-run

# List all styles and presets
bash skills/seo-images/scripts/generate.sh --list-styles
```

Requires: `REPLICATE_API_TOKEN` (or `GOOGLE_AI_API_KEY` for Google AI Studio). See skill SKILL.md for setup.

### skills/seo-health — Technical SEO Monitoring

Rankings depend on a solid technical foundation.

| Script | What It Does |
|--------|-------------|
| `health-speed.sh` | PageSpeed + Core Web Vitals (LCP, INP, CLS) |
| `health-crawl.sh` | Broken links, missing meta tags, redirect chains, mixed content |
| `health-images.sh` | Oversized images, missing alt text, wrong formats |

### skills/seo-checklist — Reference

Technical SEO reference covering meta tags, schema markup (Article, FAQ, HowTo), llms.txt, topical authority (hub-and-spoke), and Core Web Vitals thresholds.

---

## Quick Start

### Prerequisites

- [OpenClaw](https://github.com/openclaw/openclaw) installed and running
- Google Search Console access for your site
- (Optional) [DataForSEO](https://dataforseo.com) API account (~$50/month)

### 1. Clone and install

```bash
git clone https://github.com/TheMattBerman/seo-kit.git
cp -r seo-kit/skills/* ~/clawd/skills/
```

### 2. Set up auth

See [SETUP.md](./SETUP.md) for Google Search Console OAuth and DataForSEO credentials.

### 3. Run the health check

```bash
bash skills/seo-agent/scripts/seo-check.sh
bash skills/seo-health/scripts/health-speed.sh https://yoursite.com --both
```

### 4. Let the agent interview you

Tell your OpenClaw agent: *"Run the SEO Forge brand interview"*

8 questions. 5 minutes. Every article after this sounds like you.

### 5. Set it on a schedule

```
Monday:    seo-discover + seo-monitor + health checks
Tuesday:   Write content targeting top opportunities
Wednesday: link-internal (add cross-links to new content)
Thursday:  link-mine + link-mentions (find backlink targets)
Friday:    seo-compete on one competitor + link-prospect
```

---

## The Complete Loop

```
Week 1: Discover keywords → Write 3 articles → Add internal links
         Run health check → Fix any technical issues

Week 2: Monitor rankings → Write supporting content for climbers
         Mine competitor backlinks → Send outreach

Week 3: Competitor gap analysis → Find 8 new keywords
         Find unlinked mentions → Easy outreach wins

Week 4: Articles hitting page 1 → Organic traffic up
         Agent is already 3 weeks ahead of you

Repeat forever.
```

---

## API Keys and What's Free

Every script works without paid APIs. Some get better with them. Here's the breakdown:

### Free (no API key needed)

| Script | What It Uses |
|--------|-------------|
| `seo-monitor` | Google Search Console (OAuth) |
| `seo-discover` (GSC-only mode) | Google Search Console |
| `seo-check` | Google Search Console |
| `seo-interview` | Your brain |
| `health-speed` | Google PageSpeed Insights API (free, rate-limited) |
| `health-crawl` | Direct HTTP crawl |
| `health-images` | Direct HTTP crawl |
| `link-internal` | Your sitemap + direct crawl |
| All link scripts (fallback) | Web search queries (manual or via agent) |

### Google Search Console (free, requires OAuth setup)

Required for: `seo-discover`, `seo-monitor`, `seo-compete`

This is where your real ranking data comes from. Not estimates. Your actual positions, clicks, and impressions from Google. Setup takes 5 minutes. See [SETUP.md](./SETUP.md).

### DataForSEO (~$50/month, optional)

Required for full features of: `seo-discover`, `seo-compete`, `link-mine`, `link-mentions`, `link-broken`, `link-prospect`

DataForSEO is the API behind most SEO tools. Direct access costs a fraction of what Ahrefs or Semrush charge. It adds:
- **Search volumes** for discovered keywords
- **Keyword expansion** (suggestions + related keywords)
- **Competitor keyword gaps** (what they rank for, you don't)
- **SERP data** for link prospecting and mention discovery
- **Backlinks data** (separate subscription within DataForSEO)

Without it, `seo-discover` still works using GSC data alone (scored by impressions instead of search volume). Link scripts fall back to web search queries you can run manually.

Sign up at [dataforseo.com](https://dataforseo.com). Set `DATAFORSEO_LOGIN` and `DATAFORSEO_PASSWORD` in your environment.

### PageSpeed Insights API Key (free, optional)

Recommended for: `health-speed`

Without a key: rate-limited (a few requests per minute). With a free API key: 25,000 queries/day.

Get one at [Google Cloud Console](https://console.cloud.google.com/apis/credentials) and enable the PageSpeed Insights API. Set `PAGESPEED_API_KEY` in your environment.

### Replicate API (image generation, optional)

Required for: `seo-images`

Nano Banana 2 (Google Gemini 3.1 Flash Image) runs on Replicate. ~$0.02-0.05 per image at 1K, ~$0.08-0.12 at 2K.

Sign up at [replicate.com](https://replicate.com). Set `REPLICATE_API_TOKEN` in your environment.

**Alternative:** Use Google AI Studio (`GOOGLE_AI_API_KEY`) for free-tier access, or fal.ai (`FAL_KEY`). The skill generates structured prompts — pipe them to any provider.

### What You Actually Need

| Level | APIs | Monthly Cost | What Works |
|-------|------|-------------|------------|
| **Starter** | GSC only | $0 | Discovery (GSC mode), monitoring, health checks, internal links |
| **Starter + Images** | GSC + Replicate | ~$5 | Above + AI-generated article images |
| **Full** | GSC + DataForSEO | ~$50 | Everything: volumes, expansion, competitor gaps, SERP-based link prospecting |
| **Full + Images** | GSC + DataForSEO + Replicate | ~$55 | Everything + publication-quality images |
| **Full + Backlinks** | GSC + DataForSEO + Backlinks addon | ~$100 | Everything + competitor backlink mining |

Start at $0. Add DataForSEO when you want search volumes and competitor analysis.

---

## Cost Comparison

| The Old Way | The Agent Way |
|-------------|--------------|
| Semrush: $200/mo | DataForSEO: $50/mo (or $0) |
| Ahrefs: $200/mo | GSC: free |
| Surfer: $89/mo | PageSpeed API: free |
| Jasper: $80/mo | OpenClaw: free |
| SEO freelancer: $5k/mo | SEO Kit: free |
| **Total: $5,569/mo** | **Total: $0-50/mo** |

---

## File Structure

```
seo-kit/
  skills/
    seo-agent/           # Discovery + monitoring
      SKILL.md
      scripts/
        seo-discover.sh
        seo-monitor.sh
        seo-compete.sh
    seo-forge/           # Content engine
      SKILL.md
      scripts/
        seo-interview.sh
        seo-research.sh
        seo-check.sh
    seo-links/           # Backlink acquisition
      SKILL.md
      scripts/
        link-mine.sh
        link-mentions.sh
        link-broken.sh
        link-internal.sh
        link-prospect.sh
    seo-images/          # AI image generation
      SKILL.md
      scripts/
        generate.sh
      styles/
        founder_editorial.json
        dark_data.json
        product_lifestyle.json
        social_card.json
        warm_lifestyle.json
        cinematic_scene.json
        verticals.json
      references/          # Gold-standard reference images (add your own)
    seo-health/          # Technical monitoring
      SKILL.md
      scripts/
        health-speed.sh
        health-crawl.sh
        health-images.sh
    seo-checklist/       # Reference docs
      CHECKLIST.md
  SOUL.md
  AGENTS.md
  SETUP.md
  README.md
```

---

## More OpenClaw Kits

- [meta-ads-kit](https://github.com/TheMattBerman/meta-ads-kit) — AI agent that runs your Meta ads
- [first-1000-kit](https://github.com/TheMattBerman/first-1000-kit) — AI agent that finds your first 1000 customers

---

## License

MIT. Do whatever you want with it.
