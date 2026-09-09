#!/usr/bin/env python3
"""Land the 6 Otto corridor-fact batches into public.requirement_items as PENDING candidates.

Dedup BY TITLE against existing (approved+pending) rows per destination country, so we don't
duplicate facts we already hold. Mover-type scopes applies_to_nationality_classes_json:
EEA free-mover corridors -> ["EU_EEA"]; third-country -> ["THIRD_COUNTRY"]. Everything lands
review_status='pending', verification_status='corpus_grounded' (Otto-researched + cited, NOT
human-verified). Append-only: the protected fingerprint (approved/verified rows) must be
unchanged and the approved + verified counts must not move.

MODES
  --preview  (default)  READ-ONLY. Queries existing titles + counts, maps + dedups in Python,
                        prints exactly what WOULD insert per country + every dedup decision.
                        Runs NO INSERT — safe to run anywhere.
  --dry-run             BEGIN .. INSERT (ON CONFLICT id DO NOTHING) .. assert append-only .. ROLLBACK.
  --apply               same, but COMMIT.  (prod write — operator-run)

  --dedup-threshold F   Jaccard similarity (significant tokens) at/above which a new fact is treated
                        as a duplicate of an existing title. Default 0.72. Tune from the preview log.
  --country CC          restrict to one destination country (e.g. IRELAND).
"""
import argparse, json, re, sys, uuid, difflib
from datetime import datetime
from pathlib import Path

_SCRATCH_FALLBACK = Path("/private/tmp/claude-501/-Users-romainlecomte-Documents-GitHub-rolec--claude-worktrees-relopass-import-automation-4327e6/654f1ea6-ab72-4424-b9c3-30e8cf1a60e9/scratchpad/deliveries")

def deliv_dir(arg):
    """Where the *-facts.ndjson batches live: --dir if given, else a co-located src/ (the
    committed batch layout), else the session scratchpad. Makes the committed copy self-contained."""
    if arg:
        return Path(arg).expanduser()
    here = Path(__file__).resolve().parent
    return (here / "src") if (here / "src").is_dir() else _SCRATCH_FALLBACK

# batch stem -> (country_code, applies_to nationality class, corridor arrow)
CORRIDORS = {
    "no-fr": ("FRANCE",    "EU_EEA",       "NO->FR"),
    "fr-no": ("NORWAY",    "EU_EEA",       "FR->NO"),
    "es-ie": ("IRELAND",   "EU_EEA",       "ES->IE"),
    "fr-sg": ("SINGAPORE", "THIRD_COUNTRY","FR->SG"),
    "in-de": ("GERMANY",   "THIRD_COUNTRY","IN->DE"),
    "us-ec": ("ECUADOR",   "THIRD_COUNTRY","US->EC"),
}
PILLAR_MAP = {  # corridor pillar -> requirement_items PILLAR (matches the B24 landing)
    "immigration": "RESIDENCE", "residence": "IDENTITY", "tax": "EMPLOYMENT",
    "social_security": "SOCIAL_SECURITY", "healthcare": "HEALTHCARE",
}
PURPOSE = "employment"  # work-relocation context; a valid prod purpose

_STOP = set("a an the of to for in on at by and or is are be as with from your you their its it "
            "if when where within into over under after before within per not no than that this "
            "each any all must may can will shall via must".split())

def load_seed_ns():
    sys.path.insert(0, "/Users/romainlecomte/Documents/GitHub/rolec")
    from backend.scripts.seed_requirements import _SEED_NS
    return _SEED_NS

def title_of(fact_text: str) -> str:
    """A concise descriptive title = the fact's leading ~120 chars on a word boundary. A plain
    prefix (not a sentence split) so abbreviations like 'art.'/'Reg.'/'No.' don't truncate it.
    Matches the prose-title style already in prod."""
    t = " ".join(str(fact_text).split()).rstrip(" .;,:")
    if len(t) <= 120:
        return t
    return t[:120].rsplit(" ", 1)[0].rstrip(" .;,:")

def tokset(s: str) -> frozenset:
    words = re.findall(r"[a-z0-9]+", str(s).lower())
    return frozenset(w for w in words if w not in _STOP and len(w) > 2)

def jaccard(a: frozenset, b: frozenset) -> float:
    if not a or not b: return 0.0
    return len(a & b) / len(a | b)

def best_match(title_ts: frozenset, full_ts: frozenset, existing):
    """Score a new fact against every existing (title, title_tokset).
    score = max(
        Jaccard(new_title_tokens, existing_title_tokens),                # both are statements
        containment = |existing_title_tokens ∩ new_fact_tokens| / |existing_title_tokens|  # existing label covered by the new fact
    ), the containment arm only when the existing title has >=3 significant tokens (avoids a
    2-word label matching by chance). Returns (best_score, matched_title, method)."""
    best_s, best_t, best_m = 0.0, None, ""
    for et, ets in existing:
        jac = jaccard(title_ts, ets)
        cont = (len(ets & full_ts) / len(ets)) if len(ets) >= 3 else 0.0
        s, m = (jac, "jaccard") if jac >= cont else (cont, "contain")
        if s > best_s:
            best_s, best_t, best_m = s, et, m
    return best_s, best_t, best_m

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--preview", action="store_true", help="read-only plan (default)")
    ap.add_argument("--dry-run", action="store_true", help="INSERT then ROLLBACK")
    ap.add_argument("--apply", action="store_true", help="INSERT then COMMIT (prod write)")
    ap.add_argument("--dedup-threshold", type=float, default=0.85)
    ap.add_argument("--country", default=None)
    ap.add_argument("--dir", default=None, help="batch dir (default: co-located src/, else scratchpad)")
    args = ap.parse_args()
    if not (args.dry_run or args.apply):
        args.preview = True
    DELIV = deliv_dir(args.dir)

    _SEED_NS = load_seed_ns()
    from sqlalchemy import create_engine, text
    env = open("/Users/romainlecomte/Documents/GitHub/rolec/.env").read()
    db = re.search(r"^DATABASE_URL=(.+)$", env, re.M).group(1).strip().strip('"').strip("'")
    url = db.replace("postgres://", "postgresql://")
    if "sslmode" not in url: url += ("&" if "?" in url else "?") + "sslmode=require"
    eng = create_engine(url, pool_pre_ping=True)

    FP = text("""
      SELECT count(*) total,
             count(*) FILTER (WHERE review_status='approved') approved,
             count(*) FILTER (WHERE verification_status='verified') verified,
             md5(string_agg(id||coalesce(title,'')||coalesce(description,'')||coalesce(verification_status,'')||coalesce(review_status,''),'|' ORDER BY id)
                 FILTER (WHERE review_status='approved' OR verification_status='verified')) fp
      FROM public.requirement_items WHERE country_code=:cc""")
    EXISTING_TITLES = text("""SELECT title FROM public.requirement_items
                              WHERE country_code=:cc AND review_status IN ('approved','pending') AND title IS NOT NULL""")
    INS = text("""
      INSERT INTO public.requirement_items
        (id,country_code,purpose,pillar,title,description,severity,owner,required_fields_json,
         citations_json,last_verified_at,verification_status,applies_to_nationality_classes_json,
         review_status,non_obvious)
      VALUES
        (:id,:cc,:purpose,:pillar,:title,:description,'WARN','EMPLOYEE','[]',
         :citations,:lva,'corpus_grounded',:applies,'pending',false)
      ON CONFLICT (id) DO NOTHING""")

    # ---- build planned rows per country (read-only) ----
    plan = {}   # country -> {rows:[...], dedup:[(new,existing,score)], batch}
    for stem, (cc, natclass, arrow) in CORRIDORS.items():
        if args.country and cc != args.country:
            continue
        f = DELIV / f"{stem}-facts.ndjson"
        recs = [json.loads(l) for l in f.read_text().splitlines() if l.strip()]
        with eng.connect() as c:
            existing = [(r[0], tokset(r[0])) for r in c.execute(EXISTING_TITLES, {"cc": cc}).all()]
        rows, dedup, seen_titles, scores = [], [], set(), []
        for r in recs:
            ft = r.get("fact_text", "")
            title = title_of(ft)
            nt = tokset(title)
            score, matched, method = best_match(nt, tokset(ft), existing)
            scores.append(score)
            if score >= args.dedup_threshold:
                dedup.append((title, matched, round(score, 2), method))
                continue
            if title.lower() in seen_titles:            # intra-batch dup
                dedup.append((title, "(intra-batch)", 1.0, "exact")); continue
            seen_titles.add(title.lower())
            pillar = PILLAR_MAP.get(r.get("pillar", ""), "RESIDENCE")
            rid = str(uuid.uuid5(_SEED_NS, f"{cc}|{PURPOSE}|{title}"))
            citations = [{"url": r.get("source_url"), "topic_key": r.get("category") or r.get("pillar"),
                          "corridor": arrow, "quote": r.get("evidence_quote")}]
            rows.append({"id": rid, "cc": cc, "purpose": PURPOSE, "pillar": pillar, "title": title,
                         "description": r.get("fact_text"), "citations": json.dumps(citations),
                         "lva": datetime.utcnow(), "applies": json.dumps([natclass])})
            existing.append((title, nt))                # so later facts dedup against earlier-in-batch
        plan[cc] = {"rows": rows, "dedup": dedup, "recs": len(recs), "arrow": arrow,
                    "natclass": natclass, "scores": scores}

    # ---- report ----
    def band(ss, lo, hi): return sum(1 for s in ss if lo <= s < hi)
    print(f"MODE: {'APPLY' if args.apply else ('DRY-RUN' if args.dry_run else 'PREVIEW (read-only)')}   "
          f"dedup_threshold={args.dedup_threshold}\n")
    grand_new = grand_dedup = 0
    for cc, p in plan.items():
        ss = p["scores"]
        print(f"### {cc}  ({p['arrow']}, applies_to=[{p['natclass']}])  — {p['recs']} facts in batch")
        print(f"    NEW to insert: {len(p['rows'])}   |   deduped (already have): {len(p['dedup'])}")
        print(f"    best-match-score bands:  <.4:{band(ss,0,.4)}  .4-.6:{band(ss,.4,.6)}  "
              f".6-.72:{band(ss,.6,.72)}  .72-.85:{band(ss,.72,.85)}  >=.85:{band(ss,.85,1.01)}")
        for (nt, ex, sc, m) in sorted(p["dedup"], key=lambda x: -x[2]):
            print(f"      dedup {sc:>4} [{m}]  NEW: {nt[:66]}")
            print(f"                        ~= {str(ex)[:66]}")
        grand_new += len(p["rows"]); grand_dedup += len(p["dedup"])
    borderline = sum(band(p["scores"], 0.6, args.dedup_threshold) for p in plan.values())
    print(f"\nTOTAL: {grand_new} new candidate facts to insert, {grand_dedup} auto-deduped (score>={args.dedup_threshold}).")
    print(f"       {borderline} 'possible overlap' facts (score 0.6-{args.dedup_threshold}) land PENDING — the")
    print(f"       human reviewer at /admin/countries catches any true dup there (safer than silently dropping a real fact).\n")

    if args.preview:
        print("PREVIEW only — no DB writes. Review the dedup decisions + threshold, then run --dry-run (operator).")
        return 0

    # ---- dry-run / apply: insert + append-only assert, per country ----
    ok_all = True
    with eng.begin() as c:
        for cc, p in plan.items():
            b = c.execute(FP, {"cc": cc}).mappings().first()
            inserted = sum(c.execute(INS, row).rowcount for row in p["rows"])
            a = c.execute(FP, {"cc": cc}).mappings().first()
            append_ok = (a["approved"] == b["approved"] and a["verified"] == b["verified"]
                         and a["fp"] == b["fp"])
            ok_all &= append_ok
            print(f"{cc:<11} inserted={inserted:<3} approved {b['approved']}->{a['approved']} "
                  f"verified {b['verified']}->{a['verified']} total {b['total']}->{a['total']}  "
                  f"append_only={'OK' if append_ok else '!! VIOLATED'}")
        if not ok_all:
            print("\n!! append-only violated — rolling back."); raise SystemExit(2)
        if not args.apply:
            print("\nDRY RUN — rolling back (pass --apply to commit)."); raise Exception("__rollback__")
        print("\nAPPLIED — committing.")
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        if str(e) == "__rollback__":
            raise SystemExit(0)
        raise
