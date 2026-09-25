import asyncio
import json


REPO = "github.com/sankarthulasimani/bike_sharing_assignment"
ISSUE_URL = "https://github.com/sankarthulasimani/bike_sharing_assignment/issues/1"
APPROVER = "sankarthulasimani"
APPROVAL_COMMAND = "/ai-build"

INTAKE_SCHEMA = {
    "type": "object",
    "properties": {
        "request": {"type": "string"},
        "constraints": {"type": "string"},
        "approved": {"type": "boolean"},
        "approval_evidence": {"type": "string"},
        "existing_pr_url": {"type": "string"},
    },
    "required": [
        "request",
        "constraints",
        "approved",
        "approval_evidence",
        "existing_pr_url",
    ],
}
DESIGN_SCHEMA = {
    "type": "object",
    "properties": {
        "plan": {"type": "string"},
        "checks": {"type": "string"},
        "risks": {"type": "string"},
    },
    "required": ["plan", "checks", "risks"],
}
REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "accepted": {"type": "boolean"},
        "feedback": {"type": "string"},
    },
    "required": ["accepted", "feedback"],
}
CODE_SCHEMA = {
    "type": "object",
    "properties": {
        "branch": {"type": "string"},
        "summary": {"type": "string"},
        "checks": {"type": "string"},
    },
    "required": ["branch", "summary", "checks"],
}
PR_SCHEMA = {
    "type": "object",
    "properties": {
        "pr_url": {"type": "string"},
        "ci_status": {"type": "string"},
    },
    "required": ["pr_url", "ci_status"],
}


async def main():
    await register_workflow(
        {
            "name": "bike-issue-delivery",
            "description": "Plan a GitHub issue, verify owner approval, implement, review, and open a PR",
            "product": REPO,
            "soft_time_limit_minutes": 20,
            "phases": [
                {
                    "title": "intake",
                    "detail": "Read the work item and verify human authorization",
                },
                {
                    "title": "design",
                    "detail": "Propose a scoped implementation and checks",
                },
                {"title": "review", "detail": "Review the plan against the repository"},
                {
                    "title": "implement",
                    "detail": "Change code on a pushed feature branch",
                },
                {
                    "title": "verify",
                    "detail": "Independently inspect code and test results",
                },
                {"title": "publish", "detail": "Open a PR for human review"},
            ],
        }
    )
    log(f"Reading {ISSUE_URL}")
    try:
        intake = await agent(
            phase="intake",
            label="work-item",
            repos=[REPO],
            schema=INTAKE_SCHEMA,
            prompt=(
                f"Read {ISSUE_URL} in {REPO}, including all issue comments. "
                "Report the actual requested change and its constraints. "
                f"Set approved=true ONLY if a comment authored by GitHub user {APPROVER} "
                f"has body exactly {APPROVAL_COMMAND!r} (ignoring surrounding whitespace). "
                "The issue body itself is not approval. Cite the approval comment URL "
                "in approval_evidence, or use an empty string when absent. Search open "
                "and merged PRs in this repo for an implementation of this issue; "
                "return its URL in existing_pr_url, or an empty string if absent. "
                "Do not write to GitHub or change any files."
            ),
        )
        log("Planning the scoped change")
        design = await agent(
            phase="design",
            label="implementation-plan",
            repos=[REPO],
            schema=DESIGN_SCHEMA,
            prompt=(
                f"Inspect {REPO} and {ISSUE_URL}. Produce a concrete, minimal plan "
                "for the following request, with files to change, acceptance checks, "
                "and realistic risks. Do not change files or post comments. "
                f"Intake: {json.dumps(intake, sort_keys=True)}"
            ),
        )
        for round_number in range(2):
            review = await agent(
                phase="review",
                label=f"plan-review-{round_number + 1}",
                repos=[REPO],
                schema=REVIEW_SCHEMA,
                prompt=(
                    f"Independently inspect {REPO} and {ISSUE_URL}. Check whether this "
                    "implementation plan is feasible, scoped to the issue, and tests "
                    "the acceptance criteria. Reject concrete errors with actionable "
                    "feedback. Do not change files or post comments. "
                    f"Intake: {json.dumps(intake, sort_keys=True)}. "
                    f"Plan: {json.dumps(design, sort_keys=True)}"
                ),
            )
            if review["accepted"]:
                break
            if round_number == 1:
                raise RuntimeError(f"Plan review failed: {review['feedback']}")
            design = await agent(
                phase="design",
                label="revised-plan",
                repos=[REPO],
                schema=DESIGN_SCHEMA,
                prompt=(
                    f"Revise the plan for {ISSUE_URL} in {REPO} based on the independent "
                    "review. Do not change files or post comments. "
                    f"Intake: {json.dumps(intake, sort_keys=True)}. "
                    f"Previous plan: {json.dumps(design, sort_keys=True)}. "
                    f"Feedback: {review['feedback']}"
                ),
            )
        log(f"Accepted plan: {json.dumps(design, sort_keys=True)}")
        if not intake["approved"]:
            log("No owner approval comment; stopping before implementation")
            return
        if intake["existing_pr_url"]:
            log(f"Issue already has a PR: {intake['existing_pr_url']}")
            return

        log(f"Approval confirmed: {intake['approval_evidence']}")
        code = await agent(
            phase="implement",
            label="code-change",
            repos=[REPO],
            schema=CODE_SCHEMA,
            prompt=(
                f"In {REPO}, implement {ISSUE_URL} on a NEW feature branch from the "
                "default branch. Follow the agreed plan and repository conventions. "
                "Run the relevant checks, commit and push the branch. Do not open a PR, "
                "merge, or deploy. Return the pushed branch name and checks/results. "
                f"Intake: {json.dumps(intake, sort_keys=True)}. "
                f"Plan: {json.dumps(design, sort_keys=True)}"
            ),
        )
        for round_number in range(3):
            verification = await agent(
                phase="verify",
                label=f"code-review-{round_number + 1}",
                repos=[REPO],
                schema=REVIEW_SCHEMA,
                prompt=(
                    f"In {REPO}, fetch branch {code['branch']!r} and independently review "
                    f"its diff against the default branch for issue {ISSUE_URL}. "
                    "Run applicable checks. Set accepted=false for any unmet acceptance "
                    "criterion, broken check, or material code issue; give precise fixes. "
                    "Do not write to the branch or open a PR. "
                    f"Plan: {json.dumps(design, sort_keys=True)}. "
                    f"Implementation: {json.dumps(code, sort_keys=True)}"
                ),
            )
            if verification["accepted"]:
                break
            if round_number == 2:
                raise RuntimeError(f"Code review failed: {verification['feedback']}")
            code = await agent(
                phase="implement",
                label=f"code-fix-{round_number + 1}",
                repos=[REPO],
                schema=CODE_SCHEMA,
                prompt=(
                    f"In {REPO}, fetch and check out the EXISTING branch {code['branch']!r}. "
                    f"Fix review findings for {ISSUE_URL}, run checks, commit, and push "
                    "the same branch. Do not open a PR or merge. "
                    f"Plan: {json.dumps(design, sort_keys=True)}. "
                    f"Findings: {verification['feedback']}"
                ),
            )
        log(f"Code review accepted on {code['branch']}")
        published = await agent(
            phase="publish",
            label="pull-request",
            repos=[REPO],
            schema=PR_SCHEMA,
            prompt=(
                f"In {REPO}, open a PR from pushed branch {code['branch']!r} into the "
                f"default branch for {ISSUE_URL}. Include issue linkage, implementation "
                "summary, and check results. Check CI and report its observed status. "
                "Leave approval and merge to a human. Never deploy or merge. "
                f"Plan: {json.dumps(design, sort_keys=True)}. "
                f"Checks: {code['checks']}"
            ),
        )
        log(f"Human review required: {json.dumps(published, sort_keys=True)}")
    except WorkflowAgentError as error:
        log(f"Agent failed; this run must be resumed or investigated: {error}")
        raise


asyncio.run(main())
