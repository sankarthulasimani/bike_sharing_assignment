# Bike-sharing issue delivery pilot

Use this pilot for [the notebook validation work item](https://github.com/sankarthulasimani/bike_sharing_assignment/issues/1). It maps issue intake, planning, architecture review, code, testing, review and PR creation to separate Devin sessions.

Run `run_workflow` with `workflow_name="bike-issue-delivery"` and `script_path` pointing to this directory's `workflow.py`. The script produces a reviewed plan even before approval. It writes code only after the issue owner comments exactly `/ai-build` on the issue; the GitHub automation also matches that command and author.

Each agent uses a separate VM and consumes ACUs. Agent outputs feed the next stage. A failed stage stops the workflow and can be retried by resuming the run ID. Implementation and review have bounded retry loops.

| Diagram layer | This pilot |
| --- | --- |
| Work item | GitHub issue #1 and an owner-authored `/ai-build` comment |
| Context | Repository source, README, notebook, CSV, issue and comments |
| Planner / architect | Separate design and independent plan-review agents |
| Coder / tester / reviewer | Pushed feature branch, local checks, independent code review with bounded fixes |
| PR / merge | PR and CI status; human review and merge |
| Governance | Explicit approval comment, scoped repo, serial automation runs, workflow logs and PR history |

The automation starts disabled so an approval comment cannot run before this skill is merged into the default branch. After merging the installation PR, enable the automation and comment on the issue to authorize implementation. It runs as the creator, permits unattended child-session launches, allows egress to Git Manager, and emails the creator only if dispatch fails.

The PR is the second human gate: review it and require passing CI before merging. The resulting GitHub Actions job checks notebook and CSV inputs on the PR; a merge or deployment remains under repository controls. This repository has no configured production deployment or required branch check. The pilot does not provision Azure DevOps, OpenWiki, Graphy, Serena, or SRE signals; connect those sources through their supported integrations when they exist.

To adapt to another GitHub repo, copy this skill, update `REPO`, `ISSUE_URL`, and `APPROVER` in the script, and change the GitHub automation's repository/author filters to match. Do not point multiple concurrent runs at the same issue or branch.
