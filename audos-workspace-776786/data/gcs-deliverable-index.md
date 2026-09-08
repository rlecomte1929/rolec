# Otto GCS deliverable index — recovered 2026-08-13

Every URL below is **complete and working**. They were recovered by reading the
anchor `href` attributes out of the Audos DOM — the chat renders the link *text*
truncated (`…494......`) but leaves the `href` intact. No Otto round trip was
needed, and asking Otto to re-print them untruncated does not work.

**Base URL** — prepend to every filename below:

```
https://storage.googleapis.com/audos-images/workspace-media/d0c29613-9cb5-4652-9c6a-494eeed352e5/
```

---

## 1. Manifests (the entry points for `otto-loader`)

| manifest | file | rows | loader-compatible |
|---|---|--:|---|
| Master manifest v1 — pet / vehicle / domestic | `1786608004600_sy8lvg6o.json` | 156 (`manifest_rows`) | ✅ |
| Master manifest v2 — task #106792, updated | `1786609327030_fhg5r379.json` | 214 (`manifest`) | ❌ key not read by loader v5 |
| Coverage matrix — task #106792 | `1786609328717_hvf5w48j.json` | — | n/a |
| Wave 3a manifest | `1786608810393_ds7nw88c.json` | 9 (`files`) | ✅ |
| Wave 3b manifest | `1786608603215_cmlz56xd.json` | 8 (`files`) | ✅ |
| Wave 3c manifest — FI, LU, SA, QA, TR, TH | `1786609088253_t0cer947.json` | 18 (`files`) | ✅ |
| Wave 3d manifest | `1786609048639_nsxwwaps.json` | 14 (`files`) | ✅ |

## 2. Immigration requirements — per country

Each country has `requirement_entities_<CC>.json` + `requirement_facts_<CC>.json`;
the first fifteen also have a corridors CSV and two markdown reports.

| country | entities | facts | corridors CSV | reliability | roadmap |
|---|---|---|---|---|---|
| NO | `1786423182221_atcmewd9.json` | `1786423186822_94o9ayxr.json` *(308 facts)* | `1786423177732_bp04od1z.csv` | `1786423195079_y0wsz86y.md` | `1786423190814_8gjbgrxx.md` |
| FR (v2, canonical) | `1786427388022_s01vxzfs.json` | `1786427391846_5h0x9xmo.json` *(65)* | `1786427384133_nltps8jk.csv` | `1786427399297_lhjm10hc.md` | `1786427395653_0ibq0ogu.md` |
| JP | `1786424791362_aa8k5anl.json` | `1786424795131_69blxyt5.json` *(37)* | `1786424788133_2oqdzziz.csv` | `1786424802167_jtmmfro6.md` | `1786424798632_v2z4ksrm.md` |
| NZ | `1786428397865_litgn3au.json` | `1786428547748_h336s9k2.json` *(70)* | `1786428194374_bocarxw9.csv` | `1786428554967_o061tgyb.md` | `1786428551394_bkc87cdc.md` |
| AT | `1786428898852_orc0fih2.json` | `1786428902590_jbzqgvgf.json` *(68)* | `1786428894929_cjwqtmef.csv` | `1786428909879_kd45t545.md` | `1786428906536_5cq9m9qj.md` |
| DK | `1786428934276_tj6lh9ej.json` | `1786428950029_cgksf6tq.json` *(67)* | `1786428955690_ayotqqd6.csv` | `1786428965510_jcaqojq2.md` | `1786428961776_fauc7af0.md` |
| BE | `1786429152079_rgs992v5.json` | `1786429154726_uyqp4vek.json` *(49)* | `1786429156591_wfk2l5d4.csv` | `1786429160260_lu9xumnm.md` | `1786429158718_re9u6ugc.md` |
| NL | `1786429181975_zdcm86d6.json` | `1786429184803_nydspe4j.json` *(57)* | `1786429180643_xrag5tnj.csv` | `1786429186570_64zqkbir.md` | `1786429185316_navikvlr.md` |
| AU | `1786429376854_8frarnvu.json` | `1786429380169_u1b1os7p.json` *(50)* | `1786429383470_p8g1i8nu.csv` | `1786429390039_gelmgxw2.md` | `1786429386954_eoyl60j5.md` |
| CA | `1786430055561_ztuhvmr0.json` | `1786432161110_izjqyylk.json` *(50)* | `1786432167907_l4yvw6au.csv` | `1786432182250_m2c9sqqr.md` | `1786432174646_ejl94b8y.md` |
| CH | `1786533415165_pvgeq3pe.json` | `1786533420941_26kht6x3.json` *(60)* | — | — | — |
| IE | `1786544930253_xsyuluek.json` | `1786544930531_m6hyg7no.json` *(109)* | — | — | — |
| SE | `1786550750356_1tt1hy17.json` | `1786550760597_scpfegit.json` *(55)* | — | — | — |
| PT | `1786550701873_hvb5zdpf.json` | `1786550720831_k7lqekxd.json` | — | — | — |
| SG | `1786561508190_sb226i9y.json` | `1786561528620_hbb42ulm.json` *(69)* | — | — | — |
| **DE** | `1786411137659_5j99udsf.json` | `1786411139086_bbahkbfo.json` | `1786411140418_0txjl1fu.csv` | `1786411142442_wf7tfnkr.md` | `1786411143737_cfv8bgif.md` |
| **DE (second pair, later upload)** | `1786411999015_86dvnnfe.json` | `1786412000409_xds68dv0.json` | — | — | — |
| **AE** | `1786419033654_rqs3gffj.json` | `1786419066146_i5llitv9.json` | `1786418958082_ntg3wow2.csv` | `1786419076588_rsupzm8y.md` | `1786419077631_thulwf6c.md` |

⚠️ FR v1 also exists (37 facts) — `_dfk89vhh.json` / `_5h0x9xmo.json` /
`_uqmu204g.md` / `_rdtu4238.md`. Use the v2 row above.

### Countries with NO GCS file at all

**ES, GB (UK) and IT were never written to GCS.** Their research exists only as
inline text in the meeting thread — for Italy the instruction was explicitly
*"paste INLINE here (disk may not persist) … Do NOT import."* These three cannot
be loaded through the normal path; the records have to be lifted out of the chat
first.

## 3. Provider research

**Consolidated (preferred):** `relopass_providers_all_phase1.json` —
`1786567954327_pnsy0z47.json` · 1,097 rows across 13 source batches, all 17 fields.

Wave 1 FR→NO (Oslo + Paris):

| file | id |
|---|---|
| `relopass_service_catalog_records_fr_no.json` (70 rows) | `1786521126159_s4y4wvrm.json` |
| `relopass_service_catalog_entities_fr_no.json` | `1786521125498_lcj4pnfl.json` |

Phase 1A corrected / Phase 1B new Tier-1:

| batch | file |
|---|---|
| Paris + New York | `1786551593445_3pkf2zid.json` |
| Warsaw | `1786551682812_sitkj334.json` |
| Brussels + Prague | `1786551745653_smi29y3b.json` |
| Berlin + Singapore | `1786551754596_unkcyo4g.json` |
| Hong Kong + Auckland | `1786545987882_fbb0bbhi.json` |
| New York + Berlin (corrected) | `1786544817084_f03nhzt7.json` |
| Singapore + Brussels (corrected) | `1786544819442_5tzlci5v.json` |
| Copenhagen + Lisbon (corrected) | `1786544820569_yb7pp577.json` |
| Madrid + Vienna (corrected) | `1786549959769_0e3h9vjk.json` |
| Stockholm + Zurich (patched) | `1786552426058_vak352u8.json` |
| San Francisco + Los Angeles | `1786552127010_9b2ep61g.json` |
| Tokyo + Sydney | `1786552341392_nyghbfqt.json` |
| Toronto + São Paulo | `1786552643025_zzlbh5q8.json` |

### Genuinely lost

The nine "Original City-Pair Batches (Aug 12)" rows resolve to
`https://%E2%80%A6/…` — Otto typed the ellipsis into the markdown itself, so the
href never held a real URL. Not a problem: the Phase 1A corrected files above
supersede every one of them.

---

*Recovered from the Audos meeting "can you extract all the GCS deliverable URLs"
plus the seven per-country routine meetings, 2026-08-13. 92 anchors read; 92
complete URLs recovered.*
