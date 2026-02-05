# EZ-Brief Weekly Run Prompt

Run the EZ-Brief weekly research grounding process:

## Steps

1. **Fetch RSS feeds** from `inputs/rss_feeds.md` (skip feeds marked as non-working)

2. **Score each article** using the rubric in `inputs/relevance_scoring_rubric.md`
   - Apply all 7 dimensions (Industry, Function, Exec, Evidence, Source, Recency, Shareability)
   - Calculate total score (max 17)

3. **Filter** to include only articles scoring ≥10

4. **Output scored articles** using the template format from the rubric:
   - Save to `grounding/[YYYY-MM-DD]_scored_articles.md`
   - Copy to `grounding/latest.md` (overwrite)

5. **Log results** to `logs/[YYYY-MM-DD]_run_log.md`
   - Include feed fetch status
   - Note any errors or changes

6. **Commit and push** to GitHub:
   ```
   git add .
   git commit -m "Week of [YYYY-MM-DD]"
   git push
   ```

## Output Format Reference

Each scored article must include:
- Title, Source, Date, Score
- Dimension breakdown
- Signal Type (Leading/Confirming/Lagging/Contrarian/Structural)
- Time Horizon (Immediate/Mid/Long/Evergreen)
- Impacted Roles (1-3 from controlled list)
- Quotable Claims with attribution
- Key Data Points with sources
- Human Synthesis (1-2 sentences)

## Prioritization Rules

**PREFER:**
- Evidence-backed claims (data, research citations)
- Structural changes (org design, operating model)
- Quantified trends with sources

**DE-PRIORITIZE:**
- Personal opinion without data
- Vendor hype / promotional content
- "Thought leadership" without evidence

## Reference Files

- Scoring rubric: `inputs/relevance_scoring_rubric.md`
- RSS feeds: `inputs/rss_feeds.md`
- Profile context: `inputs/profile_summary.md`
