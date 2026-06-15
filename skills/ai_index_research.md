# AI Index Research Skill

Use DataElf tools only. Do not invent data or write task state outside the tools.

Preferred flow for the M1 demo:

1. Search institutions, papers, and scholars for `AI Agent` in the `half_year` window.
2. Fetch detailed institution records for the leading candidates.
3. Model searched records before trend analysis.
4. Run `analyze_trend` with `target="institution_hotness_growth"`.
5. Write at least three evidence items:
   - institution half-year hotness growth;
   - AI Agent paper signal;
   - scholar, news, award, or funding signal.
6. Call `draft_report` with at least two claims and explicit evidence IDs.

The final report must state that fixture data is mock data and not the real AI Index API.
