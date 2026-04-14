## Summary

- Add `AutoResearcher` class that identifies orphan entries (entries with no inbound links) and uses perplexity to research knowledge gaps, then synthesizes results back into wiki
- Add `auto_research` flag to `Monitor` that triggers research after each ingest cycle
- Add unit tests for both modules (33 tests passing)

## Changes

| File | Change |
|------|-------|
| `scribe/research.py` | New: AutoResearcher class |
| `scribe/monitor.py` | Added `auto_research` flag + wiring |
| `tests/test_scribe_research.py` | New test file |
| `tests/test_monitor.py` | Added flag/researcher tests |

## Usage

```python
# As standalone
researcher = AutoResearcher(store, curator, mcp_fn=mcp_call)
result = await researcher.research_gaps(max_orphans=5)

# Or via Monitor (runs perpetually)
monitor = Monitor(wiki_path, store, auto_research=True)
monitor.set_researcher(AutoResearcher(store, curator, mcp_fn=mcp_call))
monitor.start()
```

## Tests

```
tests/test_scribe_research.py    10 passed
tests/test_monitor.py         12 passed  
tests/test_scribe.py         11 passed
Total                     33 passed
```

---

To create PR manually when auth is available:
```bash
gh pr create --title "Add scribe auto-research for gap-filling in wiki" --body-file PR_DRAFT.md
```