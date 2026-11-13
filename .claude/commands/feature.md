---
description: Implement one feature end-to-end — plan, tests, implementation, review.
---

Implement the following feature for the "Which Way Today?" commute planner: $ARGUMENTS

Follow this sequence, and don't skip a step even under time pressure:

1. **Plan.** State which layer(s) this touches (router/service/repository/client on the
   backend; component/hook/type on the frontend) and the shape of any new or changed API
   contract (request/response schema). If it changes a REST endpoint's shape, call that
   out explicitly — it's a contract between frontend and backend. Keep the plan short:
   a few sentences, not a design doc. If the feature implies a non-trivial architectural
   choice (new dependency, new table, change to an existing endpoint's contract), stop and
   ask me before proceeding — don't decide silently.
2. **Tests first.** Write the pytest (backend) or equivalent frontend test(s) that define
   the expected behavior, including at least one edge case (empty input, external API
   failure, missing optional field). They should fail before implementation.
3. **Implement.** Smallest change that makes the tests pass, following existing
   conventions in the codebase (see CLAUDE.md files). Keep Dockerfiles in sync if you add
   a dependency.
4. **Verify.** Run the relevant test suite and linter for whichever side(s) you touched
   (`pytest` + `ruff check .` for backend, `npm run lint` + test runner for frontend).
   Fix failures before moving on.
5. **Review.** Run the `code-reviewer` subagent on the diff before considering this done.
   Address or explicitly dismiss (with a one-line reason) each finding.

End with a short summary: what changed, why, and one sentence I could use to explain this
decision in an interview if asked.
