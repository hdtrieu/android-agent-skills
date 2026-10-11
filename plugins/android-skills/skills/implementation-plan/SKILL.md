---
name: implementation-plan
description: Turn a feature's ticket, PRD/Confluence page, team discussions, related docs and the mobile/frontend/backend repos into a high-level implementation plan - goal and scope, gaps with decision status, end-to-end flow across repos, XS/S/M/L scope breakdown, sequencing with a Gantt and critical path, and open questions. Use for "implementation plan", "tech plan", "scope breakdown", "engineering estimate" or "solution design" requests.
---

# High-level implementation plan

Produce a planning artifact, not a detailed technical design; say so in the plan.
It lets a lead see what will be built, in which repos, roughly how long it takes,
what is on the critical path, and what still needs deciding.

## Inputs

1. **Ticket** - problem, goal, scope, acceptance criteria, links, test cases:
   `integrations.py jira issue KEY --comments 50` (see `project-integrations`).
2. **Team discussions** (Slack/Teams threads, meeting notes) - decisions and how
   settled they are, rejected alternatives, owners. Use a connected tool or ask the
   user to paste them. This is the only reliable source of decision status.
3. **PRD** (Confluence or document) - requirements, variants, data rules, edge cases:
   `integrations.py confluence page <id-or-url>`, `confluence children <id>`,
   `confluence search --title "..."`.
4. **Related docs** - adjacent designs, conventions, past estimates.
5. **Repos** - the nearest existing analogue feature, extension points, endpoints
   and models. Read local clones; otherwise `integrations.py gitlab file get <path> --ref <ref>
   --project <group/project>`.

The PRD says *what* the feature must do; the repos say *what already exists*; the
gap between them is the scope; the discussions say *which decisions are settled*.

## Output skeleton

1. Goal, with an explicit scope boundary (what it is not).
2. Gaps and proposed solutions, each with decision status.
3. Approach at a glance (reuse vs build new) and a system-flow diagram.
4. 4–6 Domain-specific sections: entities/variants, data and rules, key mechanism (flexible).
7. End-to-end flow: one tier per stage, each naming its repo.
8. Scope breakdown: `# | scope | repo | what it involves | size`.
9. Estimation, sequencing and risks, with a Gantt and the critical path.
10. Open questions.
A. Appendix: taxonomies and codebase anchors (file, endpoint, module).

## Workflow

1. **Ingest.** Fetch the ticket and links, PRD, threads and docs. Find the nearest
   analogue feature in the repos and read its touchpoints. Write a short source index.
2. **Requirements.** One testable line each; mark ambiguities as open questions.
3. **Gap analysis.** For each requirement: already done, partial, or missing in the
   analogue. Propose solutions that maximise reuse and prefer additive changes.
4. **Decision mining.** Tag each solution ✅ **Decided**, ⚠️ **Approach set** (detail
   to design) or 🔴 **Uncertain**. Anything without discussion support is Uncertain.
5. **Domain model.** Core objects, fields, result vocabulary, explicit out-of-scope.
6. **Repo mapping.** For each stage name the repo and module; classify reuse / extend / new.
7. **Scope and estimate.** Rows one person can own. Always lead with an API
   spec/contract row. Mobile rows count ×2 (Android + iOS) when both apps are in scope.
8. **Sequencing.** Contract in week 1; one serial chain per discipline; Android ∥ iOS.
   Calendar time is the longest track, not the sum. Name the critical path and one
   lever that would shorten it. Risks come from Uncertain rows and wide blast radius.

Sizing (one person per row): **XS** = 1 week, **S** = 2 weeks, **M** = 4 weeks,
**L** = 6 weeks. Size by net-new surface and blast radius, not line count; when
unsure, size up and record the risk. Person-months ≈ person-weeks ÷ 4.

## Quality bar

- Goal and scope boundary stated; every gap has a solution and a status.
- Every scope row names a repo and a size; the contract row leads; totals reconcile.
- The Gantt matches the sequencing; the critical path and one lever are named.
- Every open question traces to an Uncertain row or unresolved thread.
- Decision status was mined from discussions, not assumed from the PRD.

## Output format

Deliver one self-contained HTML file with inline CSS: header band, section cards,
status pills in the gaps table, labelled flow nodes, size pills in the scope table,
and a fixed-week Gantt colored by discipline. Publish it as an artifact or document
when the host supports that.

If an input is missing, proceed and make the gap visible. Without the repos the
scope and estimate are not grounded; without discussions decision status is
unknown. State either at the top of the plan and mark affected columns "to confirm".
