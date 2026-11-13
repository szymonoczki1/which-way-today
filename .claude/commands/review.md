---
description: Run the code-reviewer subagent against the current uncommitted diff.
---

Run the `code-reviewer` subagent against the current uncommitted changes (`git diff` and
`git status` for untracked files — do not review already-committed history unless I ask).

For each finding reported, give me:
- file + line
- the concrete failure scenario (input/state → wrong behavior)
- a suggested fix, if obvious

Then ask me which findings to fix now versus defer, rather than fixing everything
automatically — some may be out of scope for the MVP deadline.
