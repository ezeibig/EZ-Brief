#!/usr/bin/env python3
"""
EZ-Brief Mistral Edition
Automated RSS article scoring and synthesis using Mistral AI

Usage:
    python ez_brief_mistral.py                    # Run with default settings
    python ez_brief_mistral.py --model mistral-medium  # Use different model
"""

import os
import sys
import json
import feedparser
import requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

try:
    from mistralai import Mistral
except ImportError:
    print("ERROR: mistralai package not installed")
    print("Install it with: pip install mistral-client")
    sys.exit(1)


# Configuration
load_dotenv()
API_KEY = os.getenv("MISTRAL_API_KEY")
MODEL = "mistral-large-latest"
BASE_DIR  = Path(__file__).parent          # Mistral/ — inputs live here
REPO_ROOT = BASE_DIR.parent               # EZ-Brief/ — grounding/ and logs/ live here


class EZBriefMistral:
    def __init__(self, api_key: str, model: str = "mistral-large"):
        if not api_key:
            raise ValueError("MISTRAL_API_KEY not set. See MISTRAL_SETUP.md")
        
        self.client = Mistral(api_key=api_key)
        self.model = model
        self.feeds = self.load_feeds()
        self.articles = []
        self.scored_articles = []
        self.run_date = datetime.now().strftime("%Y-%m-%d")
        
    def load_feeds(self) -> list:
        """Load RSS feeds from inputs/rss_feeds.md"""
        feeds_file = BASE_DIR / "inputs" / "rss_feeds.md"
        if not feeds_file.exists():
            print(f"Warning: {feeds_file} not found")
            return []
        
        feeds = []
        with open(feeds_file) as f:
            content = f.read()
            # Extract URLs starting with http
            import re
            urls = re.findall(r'https?://[^\s\)]+', content)
            # Filter out duplicate entries and known non-working feeds
            skip_keywords = ["FAILED", "NO RSS", "BLOCKED", "STALE"]
            for url in urls:
                if not any(skip in content[max(0, content.find(url)-100):content.find(url)] for skip in skip_keywords):
                    feeds.append(url)
        
        return list(set(feeds))  # Remove duplicates
    
    def fetch_articles(self) -> list:
        """Fetch articles from all RSS feeds"""
        print(f"\n📰 Fetching RSS feeds... ({len(self.feeds)} feeds)")
        articles = []
        
        for feed_url in self.feeds:
            try:
                print(f"  ✓ {feed_url[:50]}...")
                feed = feedparser.parse(feed_url)
                
                for entry in feed.entries[:5]:  # Limit per feed to manage API usage
                    article = {
                        "title": entry.get("title", "Untitled"),
                        "link": entry.get("link", ""),
                        "source": feed.feed.get("title", "Unknown"),
                        "published": entry.get("published", "Unknown"),
                        "summary": entry.get("summary", "")[:500],  # Truncate
                    }
                    articles.append(article)
                    
            except Exception as e:
                print(f"  ✗ Error: {str(e)[:50]}")
        
        self.articles = articles
        print(f"✓ Fetched {len(articles)} articles total\n")
        return articles
    
    def score_article(self, article: dict) -> dict:
        """Score a single article using Mistral"""
        scoring_prompt = f"""
Score this article on the following 7 dimensions (0-17 total points):

Article:
Title: {article['title']}
Source: {article['source']}
Published: {article['published']}
Summary: {article['summary']}

Dimensions:
1. Industry Alignment (0-2): Target industries are CPG, Pharma, Hospitality, Food, Telecom, Retail, Luxury
2. Functional Relevance (0-3): Customer Strategy, Analytics, Marketing Transformation, AI/CX, ROI
3. Executive Applicability (0-2): Enterprise-scale strategic implications vs. tactical
4. Evidence Quality (0-3): Research quality, data, citations, case studies
5. Source Credibility (0-2): Tier 1 (McKinsey, BCG, HBR), Tier 2 (industry pubs), Tier 3 (blogs)
6. Recency (0-2): Last 7 days (2), 8-30 days (1), older (0)
7. Shareability (0-3): Quotable stats, named trends, frameworks

RESPOND ONLY with valid JSON (no markdown, no explanation):
{{
  "industry": X,
  "function": X,
  "exec": X,
  "evidence": X,
  "source": X,
  "recency": X,
  "shareability": X,
  "signal_type": "Leading|Confirming|Lagging|Contrarian|Structural",
  "time_horizon": "Immediate|Mid|Long|Evergreen",
  "reasoning": "brief explanation of score"
}}
"""
        
        try:
            response = self.client.chat.complete(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": scoring_prompt
                    }
                ],
                temperature=0.3,  # Low temperature for consistent scoring
            )
            
            response_text = response.choices[0].message.content
            # Try to extract JSON if there's extra text
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                score_data = json.loads(json_match.group())
            else:
                score_data = json.loads(response_text)
            
            total_score = sum([
                score_data.get("industry", 0),
                score_data.get("function", 0),
                score_data.get("exec", 0),
                score_data.get("evidence", 0),
                score_data.get("source", 0),
                score_data.get("recency", 0),
                score_data.get("shareability", 0),
            ])
            
            return {
                **article,
                "scores": score_data,
                "total_score": total_score,
            }
            
        except Exception as e:
            print(f"  ✗ Scoring error for '{article['title'][:30]}...': {str(e)[:50]}")
            return None
    
    def score_all_articles(self):
        """Score all fetched articles"""
        print(f"\n🤖 Scoring {len(self.articles)} articles with Mistral...")
        scored = []
        
        api_errors = 0
        for i, article in enumerate(self.articles, 1):
            print(f"  [{i}/{len(self.articles)}] {article['title'][:50]}...", end=" ")
            result = self.score_article(article)
            if result is None:
                api_errors += 1
                print(f"→ API ERROR (failed to score)")
            elif result.get("total_score", 0) >= 10:
                scored.append(result)
                print(f"→ Score: {result['total_score']}/17 ✓")
            else:
                print(f"→ Score: {result['total_score']}/17 (filtered out)")

        if api_errors > 0:
            print(f"\n⚠️  WARNING: {api_errors}/{len(self.articles)} articles failed to score (API errors)")
            print("   Check MISTRAL_API_KEY and model name if all articles failed.")

        self.scored_articles = sorted(scored, key=lambda x: x["total_score"], reverse=True)
        print(f"\n✓ {len(self.scored_articles)} articles scored ≥10\n")
    
    def format_output(self) -> str:
        """Format scored articles as markdown"""
        critical = [a for a in self.scored_articles if a["total_score"] >= 14]
        high = [a for a in self.scored_articles if 10 <= a["total_score"] < 14]
        
        output = f"""# EZ-Brief Scored Articles
**Date:** {self.run_date}
**Scoring Model:** Mistral ({self.model})
**Threshold:** Score ≥10 included

---

## CRITICAL (14-17)

"""
        
        for article in critical:
            s = article["scores"]
            roles = ", ".join(article["scores"].get("impacted_roles", ["AI/ML Leadership"])[:2])
            
            output += f"""### {article['title']}
**Source:** {article['source']} | **Date:** {article['published'][:10]} | **Score:** {article['total_score']}/17

**Breakdown:**
Industry [{s['industry']}] | Function [{s['function']}] | Exec [{s['exec']}] | Evidence [{s['evidence']}] | Source [{s['source']}] | Recency [{s['recency']}] | Shareability [{s['shareability']}]

**Signal Type:** {s.get('signal_type', 'Leading')}
**Time Horizon:** {s.get('time_horizon', 'Mid')}
**Impacted Roles / Functions:** {roles}

**Summary:**
{article['summary']}

---

"""
        
        output += f"""## HIGH (10-13)

"""
        
        for article in high:
            s = article["scores"]
            roles = ", ".join(article["scores"].get("impacted_roles", ["Customer Strategy"])[:2])
            
            output += f"""### {article['title']}
**Source:** {article['source']} | **Date:** {article['published'][:10]} | **Score:** {article['total_score']}/17

**Breakdown:**
Industry [{s['industry']}] | Function [{s['function']}] | Exec [{s['exec']}] | Evidence [{s['evidence']}] | Source [{s['source']}] | Recency [{s['recency']}] | Shareability [{s['shareability']}]

**Signal Type:** {s.get('signal_type', 'Confirming')}
**Time Horizon:** {s.get('time_horizon', 'Mid')}
**Impacted Roles / Functions:** {roles}

**Summary:**
{article['summary']}

---

"""
        
        output += f"""## SUMMARY STATISTICS

| Band | Count |
|------|-------|
| Critical (14-17) | {len(critical)} |
| High (10-13) | {len(high)} |
| **Total Included** | **{len(self.scored_articles)}** |

**Processed:** {len(self.articles)} articles from {len(self.feeds)} feeds
**Model:** {self.model}
**Date:** {self.run_date}

*Scored using EZ-Brief Mistral Edition*
"""
        
        return output
    
    def save_output(self):
        """Save scored articles to markdown files"""
        output = self.format_output()
        
        # Save dated output
        dated_file = REPO_ROOT / "grounding" / f"{self.run_date}_scored_articles.md"
        dated_file.write_text(output)
        print(f"✓ Saved: {dated_file.name}")

        # Save to latest.md
        latest_file = REPO_ROOT / "grounding" / "latest.md"
        latest_file.write_text(output)
        print(f"✓ Saved: latest.md")
    
    def create_log(self):
        """Create a run log"""
        log_entry = f"""# EZ-Brief Run Log
**Date:** {self.run_date}
**Model:** {self.model}
**Status:** Complete

## Feed Summary
- Total feeds attempted: {len(self.feeds)}
- Total articles fetched: {len(self.articles)}
- Articles scored ≥10: {len(self.scored_articles)}

## Scoring Results
- Critical (14-17): {len([a for a in self.scored_articles if a['total_score'] >= 14])}
- High (10-13): {len([a for a in self.scored_articles if 10 <= a['total_score'] < 14])}

## Notes
- Model used: {self.model}
- Temperature: 0.3 (for consistency)
- Processing time: ~{len(self.articles) * 2} seconds estimated

---
"""
        
        log_file = REPO_ROOT / "logs" / f"{self.run_date}_run_log.md"
        log_file.write_text(log_entry)
        print(f"✓ Saved: {log_file.name}")
    
    def run(self):
        """Execute full pipeline"""
        print("=" * 60)
        print("EZ-Brief Mistral Edition - Weekly Run")
        print("=" * 60)
        
        self.fetch_articles()
        self.score_all_articles()
        self.save_output()
        self.create_log()
        
        print("\n" + "=" * 60)
        print(f"✓ Complete! {len(self.scored_articles)} articles ready to review")
        print("=" * 60)


if __name__ == "__main__":
    if not API_KEY:
        print("\n❌ ERROR: MISTRAL_API_KEY not set!")
        print("\nQuick setup:")
        print("  1. Get key from https://console.mistral.ai")
        print("  2. Run: export MISTRAL_API_KEY='your-key-here'")
        print("  3. Or create .env file in this directory")
        print("\nSee MISTRAL_SETUP.md for detailed instructions\n")
        sys.exit(1)
    
    # Parse arguments
    model = MODEL
    if "--model" in sys.argv:
        idx = sys.argv.index("--model")
        if idx + 1 < len(sys.argv):
            model = sys.argv[idx + 1]
    
    try:
        runner = EZBriefMistral(api_key=API_KEY, model=model)
        runner.run()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Error: {str(e)}")
        sys.exit(1)
