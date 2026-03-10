# SEO Technical Checklist

Reference guide for the SEO Kit. The agent uses this when publishing content. You can also use it to audit existing pages.

---

## Meta Tags (Every Page)

### Title Tag
- 50-60 characters (Google truncates at ~60)
- Primary keyword near the front
- Brand name at the end: "Topic Here | Brand Name"
- Unique per page. No duplicates across your site.

### Meta Description
- 150-160 characters
- Include primary keyword naturally
- Write it like ad copy. This is your pitch in search results.
- Include a call to action or value prop

### Open Graph Tags
```html
<meta property="og:title" content="Your Title" />
<meta property="og:description" content="Your description" />
<meta property="og:image" content="https://yoursite.com/og-image.jpg" />
<meta property="og:url" content="https://yoursite.com/page" />
<meta property="og:type" content="article" />
```
Image should be 1200x630px minimum.

### Twitter Card
```html
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="Your Title" />
<meta name="twitter:description" content="Your description" />
<meta name="twitter:image" content="https://yoursite.com/twitter-image.jpg" />
```

---

## Schema Markup

Add JSON-LD schema to every article. This is how you get rich results (FAQ dropdowns, how-to steps, star ratings in search).

### Article Schema (Every Blog Post)
```json
{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "Your Article Title",
  "author": {
    "@type": "Person",
    "name": "Author Name",
    "url": "https://yoursite.com/about"
  },
  "datePublished": "2026-03-01",
  "dateModified": "2026-03-01",
  "publisher": {
    "@type": "Organization",
    "name": "Your Brand",
    "logo": {
      "@type": "ImageObject",
      "url": "https://yoursite.com/logo.png"
    }
  },
  "image": "https://yoursite.com/article-image.jpg",
  "description": "Meta description here"
}
```

### FAQ Schema (When Article Has Q&A Sections)
```json
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "What is X?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "X is..."
      }
    }
  ]
}
```

### HowTo Schema (Step-by-Step Guides)
```json
{
  "@context": "https://schema.org",
  "@type": "HowTo",
  "name": "How to Do X",
  "step": [
    {
      "@type": "HowToStep",
      "name": "Step 1",
      "text": "Do this first..."
    }
  ]
}
```

### Organization Schema (Homepage)
```json
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "Your Brand",
  "url": "https://yoursite.com",
  "logo": "https://yoursite.com/logo.png",
  "sameAs": [
    "https://twitter.com/yourbrand",
    "https://linkedin.com/company/yourbrand"
  ]
}
```

---

## llms.txt

This is the new standard for telling AI crawlers (ChatGPT, Perplexity, Claude) what your site is about. Like robots.txt but for LLMs.

Create a file at `yoursite.com/llms.txt`:

```
# Your Brand Name

> One-line description of what you do.

## About
Brief description of your company, what you sell, who you serve.

## Products / Services
- Product 1: description
- Product 2: description

## Key Content
- [Topic Guide](https://yoursite.com/guide): Description
- [Resource](https://yoursite.com/resource): Description

## Contact
- Website: https://yoursite.com
- Email: hello@yoursite.com
```

**Why this matters:** When someone asks an AI "what's the best X," you want the AI to know you exist and what you do. llms.txt is how you feed that context directly.

Also create `llms-full.txt` with more detailed content if you want AI to have deeper context about your expertise.

---

## Topical Authority

Google ranks sites that demonstrate deep expertise on a topic higher than sites that cover everything shallowly.

### Hub and Spoke Model

**Hub page:** Your main page on a broad topic (e.g., "AI Marketing Guide")
- Comprehensive, 3000-5000 words
- Links to every spoke page
- Targets the highest-volume keyword

**Spoke pages:** Specific subtopics that link back to the hub
- Focused, 1500-2500 words each
- Target long-tail variations
- Always link back to the hub page

**Example structure:**
```
Hub: "AI Marketing Automation" (2400 searches/month)
  Spoke: "AI Email Marketing Tools" (880/month)
  Spoke: "AI Social Media Scheduling" (720/month)
  Spoke: "AI Ad Copy Generation" (590/month)
  Spoke: "AI Marketing Analytics" (480/month)
  Spoke: "AI Content Personalization" (390/month)
```

### Internal Linking Rules
- Every spoke links to the hub (exact or close match anchor text)
- Hub links to every spoke (descriptive anchor text)
- Spokes link to related spokes where natural
- Use 3-5 internal links per article minimum
- Anchor text should be descriptive, not "click here"

### Topical Map
Before writing, map out your full topic:
1. Start with the broad topic (hub keyword)
2. List every subtopic you can write about
3. Group by search intent (informational, commercial, transactional)
4. Prioritize by search volume and competition
5. Write hub first, then spokes in priority order

The SEO Agent's `seo-discover` script helps build this map automatically from your existing GSC data and DataForSEO keyword clusters.

---

## Technical Basics

### Sitemap
- Submit XML sitemap to Google Search Console
- Auto-generate it (most CMS do this)
- Include all indexable pages, exclude noindex pages
- Update on every publish

### robots.txt
```
User-agent: *
Allow: /
Disallow: /admin/
Disallow: /api/
Sitemap: https://yoursite.com/sitemap.xml
```

### Canonical URLs
Every page should have a self-referencing canonical:
```html
<link rel="canonical" href="https://yoursite.com/this-page" />
```
Prevents duplicate content issues from URL parameters, trailing slashes, http vs https.

### Core Web Vitals
- **LCP** (Largest Contentful Paint): < 2.5s
- **INP** (Interaction to Next Paint): < 200ms
- **CLS** (Cumulative Layout Shift): < 0.1
- Test at: pagespeed.web.dev

### Image Optimization
- Compress all images (TinyPNG, Squoosh)
- Use WebP or AVIF format
- Add descriptive alt text with keywords where natural
- Lazy load below-the-fold images
- Specify width and height to prevent layout shift

### URL Structure
- Short, descriptive, lowercase
- Use hyphens not underscores
- Include primary keyword
- No dates in URL (content stays evergreen)
- Good: `/ai-marketing-automation`
- Bad: `/2026/03/01/the-complete-guide-to-ai-marketing-automation-tools`
