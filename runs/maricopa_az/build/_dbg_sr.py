import sys
sys.path.insert(0, ".")
import runs.maricopa_az.build.run_real_sources as m

# New sources (cache path)
evs = []
n = m.collect_new_sources(evs, ev_seq_start=0, enrichment_provider=lambda x: None)
print("collect_new_sources added", n, "-> evs has", len(evs))
bad = [e.get("raw_event_id") for e in evs if e.get("source_role") is None]
print("new-source events with source_role None:", bad)

# Full raw collect (incl probate/civil/recorder)
raw = m.collect_real_raw_events()
bad2 = [e.get("raw_event_id") for e in raw if e.get("source_role") is None]
print("raw events with source_role None:", bad2[:10], "total", len(bad2))

# Show a sample new-source event's source_role
if evs:
    print("sample new-source event source_role:", evs[0].get("source_role"))
