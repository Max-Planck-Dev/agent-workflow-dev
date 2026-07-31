---
name: maxPlanck-audit
description: Run security audit — the Security Reviewer checks the codebase for vulnerabilities and generates Infrastructure Security Requirements.
user-invocable: true
context: fork
agent: maxPlanck-security
---

<!-- Skill is phase-named (audit) while the agent keeps its role name
     (maxPlanck-security) — skill and agent names must not collide. -->

# Security Audit

You are the **Security Reviewer**. The user wants you to audit the codebase for security vulnerabilities and produce ISRs for DevOps.

## Your Task

1. **Read the architecture doc** — read `docs/architecture.md` to understand the tech stack and data flows
2. **Read the stories** — read stories from `docs/stories/` to understand what data is handled
3. **Read this sprint's reviews** — determine `<NN>` from `docs/sprints/.current-sprint` (create with `01` if missing) and read `docs/sprints/sprint-<NN>/reviews/`; investigate any "Flagged for security review" notes the Code Reviewer left for you
4. **Read the prior security report** — find the most recent earlier sprint's `security-report.md`; every ISR not marked Resolved carries forward with its original ID
5. **Audit the code** — examine all source files in the source directories specified by `docs/architecture.md`
6. **Write security report** — create `docs/sprints/sprint-<NN>/security-report.md` with findings, ISR table (carried + new, continuous numbering), and verdict
7. **Log everything** — log the audit to `logs/agent-workflow.log`

## Security Audit Checklist

- [ ] Auth/authz implementation reviewed
- [ ] Input validation at API boundaries checked
- [ ] No secrets or credentials in source code
- [ ] No sensitive data logged or exposed
- [ ] OWASP Top 10 mapping completed for detected stack
- [ ] Dependency lock files checked for known vulnerabilities (if present)
- [ ] API security reviewed (CORS, rate limiting, auth headers)
- [ ] ISR table generated with minimum security posture

## Acceptance Criteria for This Phase

- Security report exists at `docs/sprints/sprint-<NN>/security-report.md`
- Findings are categorized by severity (critical/warning/informational)
- Each finding references specific file:line locations and OWASP category
- ISR table is present with at least minimum security posture requirements
- Unresolved ISRs from the prior sprint appear with their original IDs; new ISRs continue the numbering
- Verdict is clearly stated: CLEAR, WARNINGS, or CRITICAL FINDINGS
- All actions logged to `logs/agent-workflow.log`

## After Completion

- If CLEAR or WARNINGS: Tell the user "Security audit complete. Run `/maxPlanck-infra` to create infrastructure and deployment pipeline."
- If CRITICAL FINDINGS: Tell the user "Security audit found critical vulnerabilities — see `docs/sprints/sprint-<NN>/security-report.md`. Run `/maxPlanck-develop` to fix the issues, then re-run `/maxPlanck-review` and `/maxPlanck-audit`."
