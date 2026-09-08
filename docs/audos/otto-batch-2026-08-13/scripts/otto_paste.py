#!/usr/bin/env python3
"""otto_paste.py — extract the paste-ready block from each card.

Every card file has two audiences. Above the `## The card — paste from here` rule is
context for the operator: the measurement, why the task was stuck, what the engineering
half is. Below `## When it comes back (operator)` is the ingest procedure. **Neither goes
to Otto.** Pasting the operator context would tell Otto facts about a database it cannot
see, which is exactly what the [VERIFIED]/[CLAIM] discipline exists to prevent.

This writes `cards/paste/OTTO-<X>.txt` containing only the middle — the card itself —
so the copy step is a whole-file select with nothing to trim by hand.

  usage: python3 <pack>/scripts/otto_paste.py
"""

from __future__ import annotations

import json
import os
import sys

START = "## The card — paste from here"
END = "## When it comes back (operator)"

HOW_TO_USE = """\
HOW TO USE THIS FOLDER
======================

One file here = one Otto thread. Nothing else in the pack ever goes to Otto.

  1. Clear the READY FOR REVIEW column on the Audos Tasks board first.
  2. Start a meeting -> scroll to the bottom -> General Chat.
     (The "Ping Otto" button does not open a composer.)
  3. Open ONE file from this folder. Select all, copy, PASTE into the thread.
     Do NOT attach the file. Two of four cards in an earlier batch came back with
     "The file is fetching but returning empty content" and had to be pasted anyway.
  4. One card per thread. Never two cards in one thread.
  5. Send nothing else. No preamble, no "here's some context", no follow-up nudge.
     The card is self-contained on purpose: Otto keeps no memory you can rely on
     across threads, so every rule it needs is inside the text you just pasted.

WAVE ORDER
  Wave 1 (run these four in parallel, four threads):  G  H  I  J
  Wave 2 (after wave 1's files are verified in git):  K
  Wave 3 (only once waves 1-2 prove return quality):  L  M  N


THE THREE MOMENTS YOU MUST INTERVENE
====================================

Everything else is hands-off. These three are not.

--- MOMENT 1. Otto says it cannot write files. --------------------------------

Expected on every card except OTTO-I. The card tells Otto to post the data in the
thread between markers and to NAME the write task without starting it.

BEFORE you authorise anything: copy the block between the markers (e.g. everything
between OTTO-G-ROWS-BEGIN and OTTO-G-ROWS-END) and save it to

    audos-workspace-776786/data/_threads/OTTO-<X>.thread.txt

This is not bookkeeping. A "convert-only, change not a single value" pass was
measured re-querying business registers and compiling fresh entries. The saved
block is the only thing the thread_diff gate can compare the file against. Skip it
and you have no way to tell a faithful conversion from new research wearing its
clothes.

--- MOMENT 2. Authorising the write task. -------------------------------------

Paste this, filled in. Say it in exactly these terms — a vaguer authorisation is
what drifted last time.

    Authorised: run that one write task, and only that one.

    Scope, and nothing outside it:
    - It may write exactly one path: audos-workspace-776786/data/<FILENAME>
    - It converts the block already in this thread. Nothing else is input.
    - Re-query no source. Add no row. Remove no row. Change no value, including
      whitespace and capitalisation. Invent nothing.
    - Create no further tasks. Do not use Continue in Task.
    - Do not publish. Do not push. Do not run git.
    - When done, run `ls -la audos-workspace-776786/data/` and `wc -l <path>` and
      paste the raw output verbatim. Show the file, do not describe it.

    I will diff the result against the block above line by line, so an extra row
    is a failed batch, not a bonus. If the write fails, say so plainly — a reported
    failure is worth far more to me than an unreported one.

--- MOMENT 3. Otto starts planning, or spawns a task you did not ask for. ------

It has done this: asked for six QA checks, it produced a Stripe/invoice sequencing
plan plus two self-invented tasks. Stop it immediately with:

    Stop. Do not continue that task and create no others. The card asked for
    research only. Answer in this thread with the report block as written and
    stop. If follow-on work is needed, name it — do not start it.


WHAT NEVER GOES TO OTTO
=======================

  otto-batch.json          our manifest
  schemas/                 our validation
  scripts/                 our tooling
  fixtures/                our self-tests
  the operator sections of the card files (above and below the paste block)

Otto cannot see our repo, our database, our Supabase, our Cloudflare dashboard or
our vendor accounts. Anything you tell it about them, it will repeat back to you as
established fact. The measurements it needs are already inside each card, stated as
measurements — that is the whole reason the cards are written the way they are.


WHEN A CARD COMES BACK
======================

    bash docs/audos/otto-batch-2026-08-13/scripts/otto_recover.sh OTTO-<X>
    python3 docs/audos/otto-batch-2026-08-13/scripts/otto_verify.py \\
        --batch docs/audos/otto-batch-2026-08-13/otto-batch.json \\
        --card OTTO-<X> --check-urls

On PASS: run the card's reintegration steps and move the Notion task
Otto ready -> Human Review.
On FAIL: fix or drop the failing rows. Do NOT re-issue the research — it fixes
neither cause and buys you a second confident report.
If the card refutes its own premise (most likely OTTO-L): Needs Human Clarification.
"""


def main() -> int:
    pack = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.join(pack, "cards", "paste")
    os.makedirs(out_dir, exist_ok=True)

    with open(os.path.join(pack, "otto-batch.json"), encoding="utf-8") as fh:
        batch = json.load(fh)

    with open(os.path.join(out_dir, "000-HOW-TO-USE.txt"), "w", encoding="utf-8") as fh:
        fh.write(HOW_TO_USE)

    status = 0
    for card in batch["cards"]:
        src = os.path.join(pack, card["card_file"])
        with open(src, encoding="utf-8") as fh:
            text = fh.read()

        if START not in text or END not in text:
            print(f"FAIL  {card['card_id']}: missing a paste marker in {card['card_file']}")
            status = 1
            continue

        body = text.split(START, 1)[1].split(END, 1)[0].strip()

        # Belt and braces: the operator sections name systems Otto cannot see. If a
        # phrase from them survives the split, the markers moved and the extract is unsafe.
        for leak in ("(operator context)", "**Unblocks:**", "Paste from the rule down."):
            if leak in body:
                print(f"FAIL  {card['card_id']}: operator context leaked into the paste block")
                status = 1

        wave = card["wave"]
        dst = os.path.join(out_dir, f"wave{wave}-{card['card_id']}.txt")
        with open(dst, "w", encoding="utf-8") as fh:
            fh.write(body + "\n")
        print(f"  {card['card_id']}  wave {wave}  ->  cards/paste/{os.path.basename(dst)}"
              f"  ({len(body.splitlines())} lines)")

    print("\nPaste ONE of these per thread. Read 000-HOW-TO-USE.txt first.")
    return status


if __name__ == "__main__":
    sys.exit(main())
