"""Who owns a corridor step — including when nobody is there to own it.

The FR->NO corridor never exercised a case where the employer has obligations but
isn't participating. NO->FR does: registering with URSSAF (or delegating under
Reg. 987/2009 Art. 21) and the permanent-establishment question are structurally
the EMPLOYER's, but in an unsupported move no employer or HR actor is engaged on
the case at all.

An EMPLOYEE/EMPLOYER/BOTH trichotomy has no way to say that, so those obligations
end up either invisible or — far worse — quietly reassigned to the employee, who
cannot discharge them and should never be told they must.

The rule this module encodes:

    An empty HR layer does NOT transfer its obligations downward.
    It leaves them visibly ORPHANED until the HR layer is engaged.

So EMPLOYER_ABSENT is a first-class state that keeps the obligation *surfaced*
(with a forwardable brief) while keeping it *off the employee's task list*.
Resolution happens at read time; the corridor template is never rewritten, so
engaging an employer later simply re-resolves.
"""
from __future__ import annotations

from typing import Iterable, List

EMPLOYEE = "EMPLOYEE"
EMPLOYER = "EMPLOYER"
BOTH = "BOTH"
EMPLOYER_ABSENT = "EMPLOYER_ABSENT"


def resolve_responsible_party(authored: str, *, employer_engaged: bool) -> str:
    """Resolve a step's authored responsible party against the case.

    With no employer engaged, an EMPLOYER-owned step becomes EMPLOYER_ABSENT.
    A step authored EMPLOYER_ABSENT stays absent regardless: it is authored that
    way precisely because it is the employer's even in a supported move, and
    engaging an employer makes it theirs to *do*, not ours to hide.

    BOTH is deliberately NOT downgraded: the employee genuinely has their own
    half to act on, so collapsing it to EMPLOYER_ABSENT would hide real work.
    """
    party = (authored or "").strip().upper()
    if employer_engaged:
        return EMPLOYER if party == EMPLOYER_ABSENT else party
    if party == EMPLOYER:
        return EMPLOYER_ABSENT
    return party


def is_employee_actionable(resolved_party: str) -> bool:
    """True when this step belongs on the EMPLOYEE's task list.

    EMPLOYER_ABSENT is the whole point: it must be visible, but it must never
    render as an employee checkbox. Asking someone to tick off their employer's
    URSSAF registration is asking them to lie.
    """
    party = (resolved_party or "").strip().upper()
    return party in (EMPLOYEE, BOTH)


def employer_owned(resolved_parties: Iterable[str]) -> List[bool]:
    """Which of these steps are the employer's to act on (present or absent)."""
    return [
        (p or "").strip().upper() in (EMPLOYER, EMPLOYER_ABSENT)
        for p in resolved_parties
    ]
