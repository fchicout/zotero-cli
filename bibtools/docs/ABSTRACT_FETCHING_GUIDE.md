# Abstract Fetching Guide

## Overview

The `fetch_abstracts.py` tool searches for missing abstracts across multiple academic APIs and updates your Zotero library.

## API Sources (in order of priority)

1. **Springer API** ⭐ (Best for Springer content - RECOMMENDED)
2. **OpenAlex** (Free, no key needed)
3. **CrossRef** (Free, no key needed)
4. **Semantic Scholar** (Free, no key needed)
5. **Europe PMC** (Free, no key needed, good for biomedical)
6. **DOI.org scraping** (Last resort, less reliable)

## Getting a Springer API Key (RECOMMENDED)

Since your collection is from Springer, getting a Springer API key will significantly improve results.

### Steps:

1. Go to https://dev.springernature.com/
2. Click "Sign Up" (top right)
3. Create a free account
4. After logging in, go to "Applications"
5. Click "Register a new application"
6. Fill in:
   - Application name: "Zotero Abstract Fetcher"
   - Description: "Personal tool to fetch abstracts for research"
7. You'll receive an API key immediately
8. **Free tier limits**: 5,000 requests per day (more than enough)

### Add to your .env.local file:

```bash
SPRINGER_API_KEY=your_springer_api_key_here
```

## Usage

### With Springer API (RECOMMENDED):

```bash
python -m bibtools.cli.fetch_abstracts \
  --api-key yP1MW7wS6pkY2qXBK2gOcNHq \
  --library-id 6287212 \
  --library-type group \
  --collection 6WXB8QRV \
  --springer-api-key YOUR_SPRINGER_KEY \
  --limit 10000
```

### Without Springer API (current setup):

```bash
python -m bibtools.cli.fetch_abstracts \
  --api-key yP1MW7wS6pkY2qXBK2gOcNHq \
  --library-id 6287212 \
  --library-type group \
  --collection 6WXB8QRV \
  --limit 10000
```

### Dry run first (recommended):

```bash
python -m bibtools.cli.fetch_abstracts \
  --api-key yP1MW7wS6pkY2qXBK2gOcNHq \
  --library-id 6287212 \
  --library-type group \
  --collection 6WXB8QRV \
  --springer-api-key YOUR_SPRINGER_KEY \
  --limit 10000 \
  --dry-run
```

## Current Results

Without Springer API:
- 97 items without abstracts
- 3 found (3% success rate)
- All from Semantic Scholar

**Expected with Springer API:**
- Should find 60-80% of abstracts (most are Springer papers)

## Why some abstracts might not be found:

1. **Very recent papers** (2025) - not yet indexed
2. **Conference papers** - sometimes abstracts not in APIs
3. **Paywalled content** - some publishers don't share abstracts
4. **Indexing delay** - can take weeks/months after publication

## Alternative: Manual import

If APIs don't work, you can:
1. Export items from Zotero
2. Manually add abstracts from Springer website
3. Re-import to Zotero

## Rate Limiting

The script includes 0.5 second delays between requests to be respectful to APIs. For 97 items, expect ~1 minute runtime.

## Troubleshooting

### "Not found" for most items
- Get a Springer API key (most important!)
- Check if papers are very recent (2024-2025)
- Verify DOIs are correct in Zotero

### API errors
- Check internet connection
- Verify API keys are correct
- Try again later (APIs might be down)

### Rate limiting errors
- Increase delay in code (change `time.sleep(0.5)` to `time.sleep(1.0)`)
- Run in smaller batches (use `--limit 50`)
