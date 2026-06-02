"""Parker-J: data-to-text NLG — deterministic KPI summaries."""
from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.nlg.data_to_text import KPI, KPISet, summarise_kpis  # noqa: E402


def _six_kpi_fixture() -> KPISet:
    return KPISet(
        period_label="Q2 2026",
        kpis=[
            KPI("compliance", "Policy compliance", 82, prior=78, target=90, unit="%"),
            KPI("active", "Active assignments", 140, prior=120, unit=""),
            KPI("overage", "Average overage", 1200, prior=400, unit="EUR",
                higher_is_better=False, anomaly=True),
            KPI("csat", "Employee CSAT", 4.4, prior=4.5, target=4.6, unit=""),
            KPI("ttf", "Time to fill (days)", 31, prior=33, unit="d", higher_is_better=False),
            KPI("exceptions", "Open exceptions", 7, prior=7, unit=""),
        ],
    )


def test_exec_snapshot():
    out = summarise_kpis(_six_kpi_fixture(), audience="exec")
    expected = (
        "Executive summary for Q2 2026. "
        "Average overage rose to 1200 EUR and is flagged as anomalous. "
        "Active assignments rose to 140 (up 20), a favourable move. "
        "Policy compliance rose to 82% (up 4%), a favourable move; target is 90% (not yet met). "
        "Time to fill (days) fell to 31 d (down 2 d), a favourable move."
    )
    assert out == expected


def test_hr_ops_snapshot():
    out = summarise_kpis(_six_kpi_fixture(), audience="hr-ops")
    expected = (
        "Operational KPIs for Q2 2026. "
        "Anomaly: Average overage rose to 1200 EUR and is flagged as anomalous. "
        "Active assignments rose to 140 (up 20). "
        "Policy compliance rose to 82% (up 4%); target is 90% (not yet met). "
        "Time to fill (days) fell to 31 d (down 2 d)."
    )
    assert out == expected


def test_anomaly_leads_regardless_of_delta_size():
    # The anomaly has a smaller |delta| than 'active' but must still lead.
    ks = KPISet(
        "May",
        [
            KPI("active", "Active assignments", 300, prior=100, unit=""),  # |delta| 200
            KPI("flag", "Flagged metric", 11, prior=10, unit="", anomaly=True),  # |delta| 1
        ],
    )
    out = summarise_kpis(ks, audience="exec")
    first_sentence = out.split(". ")[1]
    assert first_sentence.startswith("Flagged metric")


def test_salience_orders_by_absolute_delta():
    ks = KPISet(
        "May",
        [
            KPI("small", "Small mover", 12, prior=10, unit=""),  # |delta| 2
            KPI("big", "Big mover", 90, prior=10, unit=""),  # |delta| 80
        ],
    )
    out = summarise_kpis(ks, audience="hr-ops")
    assert out.index("Big mover") < out.index("Small mover")


def test_determinism_identical_bytes():
    ks = _six_kpi_fixture()
    a = summarise_kpis(ks, audience="exec")
    b = summarise_kpis(ks, audience="exec")
    assert a == b
    assert a.encode("utf-8") == b.encode("utf-8")


def test_empty_kpi_set_is_safe():
    out = summarise_kpis(KPISet("Q3 2026", []), audience="exec")
    assert out == "No KPIs were reported for Q3 2026."


def test_three_to_five_sentences():
    # Opener + at most 4 KPI sentences = 3..5 sentences total.
    out = summarise_kpis(_six_kpi_fixture(), audience="exec")
    sentences = [s for s in out.split(". ") if s]
    assert 3 <= len(sentences) <= 5
