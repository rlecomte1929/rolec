# Editing CI workflows (`.github/workflows/*`)

## The constraint

GitHub **refuses any push whose diff modifies `.github/workflows/*` unless the
pushing credential carries the `workflow` scope.** The token used in this
environment is a `gh` **OAuth token** with scopes `gist, read:org, repo` — no
`workflow`. So pushes that touch a workflow file are rejected:

```
! [remote rejected]  <branch> -> <branch>
  (refusing to allow an OAuth App to create or update workflow
   `.github/workflows/ci.yml` without `workflow` scope)
```

The rejection applies to the **whole push** — if a commit mixes a workflow edit
with product code, the code is blocked too. (First hit: AIQ-853, where a new test
couldn't be added to the CI P1 list.)

## The fix (repo owner, one-time)

Re-authorize the existing `gh` OAuth token, adding the `workflow` scope. Run it in
your own terminal (it opens a browser / device prompt you must complete):

```bash
gh auth refresh -h github.com -s workflow
```

Verify:

```bash
gh auth status        # "Token scopes:" should now include 'workflow'
```

Alternatives if you don't use `gh`'s OAuth token for git:
- **Classic PAT** → regenerate/edit it to include the `workflow` scope.
- **Fine-grained PAT / GitHub App** → grant the **"Workflows: read and write"**
  permission, then re-approve/re-install.

After the scope is present, pushes that edit workflow files succeed normally.

## Process until the scope is universal

Even with the fix above, contributors (and AI agents) may run under a token that
lacks `workflow`. To avoid a mid-PR rejection that blocks unrelated code:

> **Keep workflow-file edits in a separate commit/PR from product code.**

That way, if a push is rejected for the workflow scope, only the workflow change
is blocked — the code lands. The pre-push hook (`.githooks/pre-push`) prints a
**warning** when a push touches `.github/workflows/*`, naming this scope
requirement, so the rejection is anticipated rather than surprising.

If an agent needs a CI change it can't push, the convention is: ship the code
without the workflow edit, and leave a one-line follow-up (e.g. *"add
`tests/<x>.py` to the CI P1 list — needs `workflow` scope"*) for a human to apply.
