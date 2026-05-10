"""
Centralized notification and escalation thresholds.
Used by the ops notification rules engine.
"""
from __future__ import annotations

# Critical queue item unassigned threshold (hours)
CRITICAL_UNASSIGNED_HOURS = 4

# High-priority unassigned threshold (hours)
HIGH_UNASSIGNED_HOURS = 12

# Critical item unresolved threshold (hours)
CRITICAL_UNRESOLVED_HOURS = 24

# Blocked item aging threshold (hours)
BLOCKED_TOO_LONG_HOURS = 48

# Repeated reopen count before escalation
REOPEN_ESCALATION_COUNT = 2

# Repeated crawl failure count before escalation
CRAWL_FAILURE_ESCALATION_COUNT = 3

# Retrigger cooldown (seconds) - avoid re-alerting too often for same issue
RETRIGGER_COOLDOWN_SECONDS = 900  # 15 minutes

# Backlog threshold for high-backlog notification
BACKLOG_HIGH_THRESHOLD = 50

# Critical backlog threshold
BACKLOG_CRITICAL_THRESHOLD = 100
