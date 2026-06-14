"""Data-to-text NLG — deterministic executive summaries from a KPI set.

Parker NLG approach #3 (data-to-text). Turns a structured set of KPIs (current
value, prior value, delta, target, anomaly flag) into a 3-5 sentence prose
summary. No LLM call, no randomness: identical input always yields identical
output. Sentences are ordered by *salience* — anomalies always lead, then the
remaining KPIs by descending absolute delta.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional, Sequence

Audience = Literal["exec", "hr-ops"]


@dataclass(frozen=True)
class KPI:
    """One metric. `delta` is current - prior; supply it or it is derived."""

    key: str
    label: str
    current: float
    prior: Optional[float] = None
    target: Optional[float] = None
    anomaly: bool = False
    unit: str = ""
    higher_is_better: bool = True

    @property
    def delta(self) -> Optional[float]:
        if self.prior is None:
            return None
        return self.current - self.prior

    @property
    def abs_delta(self) -> float:
        d = self.delta
        return abs(d) if d is not None else 0.0


@dataclass(frozen=True)
class KPISet:
    period_label: str
    kpis: Sequence[KPI]


def _fmt(value: float, unit: str) -> str:
    # Whole numbers render without a trailing .0; otherwise one decimal place.
    rounded = round(value, 1)
    num = str(int(rounded)) if rounded == int(rounded) else f"{rounded:.1f}"
    if unit == "%":
        return f"{num}%"
    if unit in ("", None):
        return num
    return f"{num} {unit}"


def _direction_word(kpi: KPI) -> str:
    d = kpi.delta
    if d is None or d == 0:
        return "held steady at"
    return "rose to" if d > 0 else "fell to"


def _is_favourable(kpi: KPI) -> Optional[bool]:
    d = kpi.delta
    if d is None or d == 0:
        return None
    improved = (d > 0) if kpi.higher_is_better else (d < 0)
    return improved


def _salience_key(kpi: KPI):
    # Anomalies first (True sorts before False via negation), then by |delta|
    # descending, then key for a stable, deterministic tie-break.
    return (not kpi.anomaly, -kpi.abs_delta, kpi.key)


def _sentence_for(kpi: KPI, *, audience: Audience) -> str:
    value = _fmt(kpi.current, kpi.unit)
    if kpi.anomaly:
        lead = "Anomaly: " if audience == "hr-ops" else ""
        return f"{lead}{kpi.label} {_direction_word(kpi)} {value} and is flagged as anomalous."

    d = kpi.delta
    if d is None:
        # No prior value to compare against — state it plainly. A label:value
        # form reads calmly and avoids the robotic, repetitive "X stands at N.
        # Y stands at N." when several KPIs lack a prior (e.g. a fresh period).
        base = f"{kpi.label}: {value}"
    else:
        delta_txt = _fmt(kpi.abs_delta, kpi.unit)
        move = "up" if d > 0 else ("down" if d < 0 else "flat")
        if move == "flat":
            base = f"{kpi.label} held steady at {value}"
        else:
            base = f"{kpi.label} {_direction_word(kpi)} {value} ({move} {delta_txt})"

    fav = _is_favourable(kpi)
    if audience == "exec" and fav is not None:
        base += ", a favourable move" if fav else ", which needs attention"

    if kpi.target is not None:
        target_txt = _fmt(kpi.target, kpi.unit)
        on_track = (kpi.current >= kpi.target) if kpi.higher_is_better else (kpi.current <= kpi.target)
        base += f"; target is {target_txt} ({'met' if on_track else 'not yet met'})"

    return base + "."


def summarise_kpis(kpis: KPISet, *, audience: Audience = "exec") -> str:
    """Render a deterministic 3-5 sentence summary of a KPI set.

    Sentences are ordered by salience: anomalies first, then descending |delta|.
    `audience` tunes tone — 'exec' adds favourability framing, 'hr-ops' is terser
    and labels anomalies explicitly.
    """
    items: List[KPI] = sorted(kpis.kpis, key=_salience_key)
    if not items:
        return f"No KPIs were reported for {kpis.period_label}."

    opener = (
        f"Executive summary for {kpis.period_label}."
        if audience == "exec"
        else f"Operational KPIs for {kpis.period_label}."
    )

    # Body: cap at 4 KPI sentences so the whole stays within 3-5 sentences.
    body = [_sentence_for(k, audience=audience) for k in items[:4]]
    return " ".join([opener, *body])
