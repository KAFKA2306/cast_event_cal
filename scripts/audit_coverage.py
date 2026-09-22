#!/usr/bin/env python3
import argparse,json
from collections import defaultdict
from pathlib import Path

STATUSES={"found","not_found","unsupported","source_unavailable"}
REASONS={"query_vocabulary_miss","result_window_ranking_miss","engagement_threshold_miss","parser_miss","classifier_reject","dedupe_identity_mismatch"}

def load(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def identities(event):
    return {str(event.get(k,"")) for k in ("event_identity","canonical_identity","id") if event.get(k)}
def audit(gold,run):
    events=run.get("events",[]); supported=set(run.get("supported_sources",[])); unavailable=set(run.get("source_unavailable",[])); misses=run.get("miss_reasons",{})
    seen=set().union(*(identities(e) for e in events)) if events else set()
    rows=[]
    for item in gold["items"]:
        ident=item["event_identity"]; expected=set(item.get("expected_sources",[])); status="found" if ident in seen else None; reason=None
        if status is None and expected and expected <= unavailable: status="source_unavailable"
        if status is None and supported and expected and not (expected & supported): status="unsupported"
        if status is None:
            status="not_found"; reason=misses.get(ident,"query_vocabulary_miss")
            if reason not in REASONS: raise ValueError(f"invalid miss reason for {ident}: {reason}")
        rows.append({"event_identity":ident,"status":status,"miss_reason":reason,"category":item["category"],"expected_sources":sorted(expected)})
    def groups(key,values):
        out={}
        for value in sorted(values):
            subset=[r for r in rows if (r[key]==value if key=="category" else value in r["expected_sources"])]
            measurable=[r for r in subset if r["status"] in {"found","not_found"}]
            out[value]={"found":sum(r["status"]=="found" for r in measurable),"measurable":len(measurable),"recall":(sum(r["status"]=="found" for r in measurable)/len(measurable) if measurable else None),"source_unavailable":sum(r["status"]=="source_unavailable" for r in subset),"unsupported":sum(r["status"]=="unsupported" for r in subset)}
        return out
    cats={r["category"] for r in rows}; sources={s for r in rows for s in r["expected_sources"]}
    return {"schema_version":"cast-event-cal.coverage-audit.v1","items":rows,"by_category":groups("category",cats),"by_source":groups("source",sources)}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--gold",default="config/coverage_gold.json"); ap.add_argument("--run",required=True); ap.add_argument("--output"); ap.add_argument("--baseline-report")
    a=ap.parse_args(); report=audit(load(a.gold),load(a.run))
    if a.baseline_report:
        base=load(a.baseline_report); before={x["event_identity"]:x["status"] for x in base.get("items",[])}
        report["delta"]=[{"event_identity":x["event_identity"],"before":before.get(x["event_identity"]),"after":x["status"]} for x in report["items"] if before.get(x["event_identity"])!=x["status"]]
    text=json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n"
    if a.output: Path(a.output).write_text(text,encoding="utf-8")
    else: print(text,end="")
if __name__=="__main__": main()
