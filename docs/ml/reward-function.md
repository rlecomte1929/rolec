# Reward function (RP-K-002)

Formal weights for internal ops. Product only emits events; it does not compute R in the SPA.

```
R = 0.3 × relief_moment_yes_rate
  + 0.4 × requirements_verified_correct_rate
  + 0.3 × cases_completed_without_compliance_issues
```

Calibrate after 50 cases. Per-corridor sample of 20 before treating relief-moment as actionable.

## Events

| Event | Where | Owner |
|---|---|---|
| `case_roadmap_reviewed` | Employee roadmap V2 fetch | employee |
| `relief_moment_captured` | `ReliefMomentCapture` | employee |
| `case_completed` | Last roadmap task ticked (`outcome=roadmap_fully_completed`) | employee (v0) |

Post-move **compliance** outcome is still an ops gap: HR must log missed requirements separately. Do not pretend `roadmap_fully_completed` means a clean legal outcome.

Free-text comments on the relief screen stay in the browser. They are not sent to PostHog.
