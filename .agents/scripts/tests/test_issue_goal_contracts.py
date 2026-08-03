"""Static contracts for issue-centered command documentation."""

import re
from pathlib import Path


ROOT = Path(__file__).parents[3]
COMMANDS = ROOT / ".agents" / "commands"
ISSUE_FORMS = ROOT / ".github" / "ISSUE_TEMPLATE"


def command(name: str) -> str:
    """Read one command contract."""
    return (COMMANDS / name).read_text(encoding="utf-8")


def test_issue_contract_guards_selection_and_remote_creation():
    content = command("issue.md")

    for text in (
        "existing",
        "create",
        "duplicate",
        ".github/ISSUE_TEMPLATE/",
        "readiness",
        "open",
        "roadmap",
        "confirm",
        "issue create",
        "unclaimed",
    ):
        assert text in content, text

    for text in ("_common-github-ownership.md", "--add-assignee"):
        assert text not in content, text


def test_issue_selects_a_target_without_dispatching_goal_and_local_delivery_is_gated():
    issue = command("issue.md")
    goal = command("goal.md")
    create_pr = command("create-pr.md")

    assert "local:<lower-kebab-id>" in issue
    assert "@.agents/commands/goal.md" not in issue
    assert "local target" in goal
    assert "--auto-merge" in goal
    assert "administrator merge authorization" in goal
    assert "promoted" in create_pr
    assert "Before any `git push`" in create_pr
    assert "unpromoted, incomplete, malformed, unreviewed, or conflicting" in create_pr
    assert "local_issue.py promote <lower-kebab-id>" in create_pr


def test_remote_specs_contracts_link_and_exclude_specs_issues():
    assert "`spec`-labelled" in command("issue.md")
    assert "set-specs" in command("plan.md")
    assert "link the primary issue" in command("plan.md")
    assert "remote references" in command("implement.md")
    assert "Specs: #<number>" in command("create-pr.md")
    assert "spec`-labelled" in command("goal.md")
    assert "Specs Issue" in (ROOT / ".agents/templates/PR-body.md").read_text()


def test_specs_delivery_contract_reconciles_before_pr_and_closes_the_exact_specs_issue():
    goal = command("goal.md")
    remote_goal = goal.split("For remote targets, use the following phases:", 1)[1]
    create_pr = command("create-pr.md")
    template = (ROOT / ".agents/templates/PR-body.md").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/close-linked-specs.yml").read_text(
        encoding="utf-8"
    )

    assert "final Specs synchronization" in goal
    assert "reconcile" in goal
    assert remote_goal.index("final Specs synchronization") < remote_goal.index(
        "@.agents/commands/create-pr.md"
    )
    assert "every workflow phase" in command("plan.md")
    assert "without transitioning backward" in command("plan.md")
    assert "Closes #<Specs number>" in create_pr
    assert "Delivery PR: <url>" in create_pr
    assert "verified final PR URL" in create_pr
    assert "preserve any `Delivery PR: <url>`" in command("plan.md")
    assert "`Closes #N` (Specs issue)" in template
    for text in (
        "pull_request:",
        "types: [closed]",
        "issues: write",
        "context.payload.pull_request",
        "Delivery PR:",
        "spec.data.state !== \"open\"",
        "label.name === \"spec\"",
        "references.length !== 1",
        "const marker = `Delivery PR: ${pr.html_url}`",
    ):
        assert text in workflow, text
    assert "pr.merged" not in workflow


def test_closed_draft_delivery_pr_is_not_excluded_from_specs_closure():
    workflow = (ROOT / ".github/workflows/close-linked-specs.yml").read_text(
        encoding="utf-8"
    )

    assert "pr.draft" not in workflow


def test_remote_pr_bodies_use_only_validated_current_specs_documents():
    content = command("create-pr.md")

    assert "workflow_state.specs.documents" in content
    assert "validated" in content
    assert "local profile" in content


def test_plan_contract_previews_and_confirms_remote_specs_mutations():
    content = command("plan.md")

    for text in (
        "Preview the exact remote Specs mutations",
        "create the `spec` label",
        "create or reuse the Specs issue",
        "link the primary issue",
        "create only missing canonical document comments",
        "edit only changed indexed comments",
        "write the completed Specs index once",
        "fresh remote-write confirmation",
        "inherited `--auto`",
    ):
        assert text in content, text


def test_implementation_issue_forms_capture_acceptance_and_validation():
    for name in ("bug_report.yml", "feature_request.yml"):
        content = (ISSUE_FORMS / name).read_text(encoding="utf-8")
        assert "Acceptance Criteria" in content, name
        assert "Validation" in content, name


def test_plan_and_implement_resolve_issue_state_and_artifacts():
    for name in ("plan.md", "implement.md"):
        content = command(name)
        assert "OWNER/REPO#NUMBER" in content
        assert "workflow_state.py show" in content
        assert "state artifacts" in content.lower()
        assert "workflow_state.py resolve-active --format json" in content

    assert "workflow_state.py set-artifacts" in command("plan.md")
    implement = command("implement.md")
    for text in ("complete plan artifacts", "commit", "push", "separate sibling PR delivery"):
        assert text in implement, text


def test_goal_and_implement_initialize_acquired_target_state_before_reading_it():
    for name in ("goal.md", "implement.md"):
        content = command(name)

        acquire = content.index("resolve-target-worktree.py")
        issue_init = content.index(
            "preflight-goal.py OWNER/REPO#NUMBER"
            if name == "goal.md"
            else "workflow_state.py init OWNER/REPO#NUMBER"
        )
        issue_show = content.index("workflow_state.py show OWNER/REPO#NUMBER")
        pr_init = content.index("workflow_state.py init-pr OWNER/REPO!NUMBER")
        plan_head = content.index(
            "workflow_state.py validate-plan-head OWNER/REPO!NUMBER"
        )

        assert acquire < issue_init < issue_show, name
        assert acquire < pr_init < plan_head, name
        assert "otherwise run `uv run python .agents/scripts/workflow_state.py show" not in content


def test_create_pr_contract_owns_single_and_stack_linkage_and_permissions():
    content = command("create-pr.md")

    for text in (
        "single",
        "full stack",
        "create or update",
        "Closes",
        "final PR",
        "Refs",
        "earlier",
        "Preview",
        "push",
        "separate",
        "remote write",
        "workflow_state.py set-pr",
        "workflow_state.py resolve-active --format json",
        "--draft",
        "_common-github-ownership.md",
        "preserve",
        "specs-delivery.json",
        "repos/OWNER/REPO/issues/<Specs number>",
    ):
        assert text in content, text


def test_create_pr_contract_rejects_spec_issues():
    content = command("create-pr.md")

    assert "non-`spec`-labelled" in content
    assert content.index("non-`spec`-labelled") < content.index(
        "Prepare one filled PR body"
    )


def test_goal_contract_is_resumable_autonomous_and_merge_ready():
    content = command("goal.md")

    for text in (
        "exactly one",
        "workflow_state.py show",
        "resume",
        "@.agents/commands/implement.md",
        "one complete run authorization",
        "baseline review",
        "mechanically clear",
        "@.agents/commands/review-implement.md",
        "@.agents/commands/review-validate.md",
        "goal_delivered",
        "clean merge-ready PR",
        "workflow_state.py resolve-active --format json",
        "_common-github-ownership.md",
        "issue body",
        "PR body",
    ):
        assert text in content, text

    assert "<type>/<issue-number>-<lower-kebab-slug>" in content
    assert "use the acquired returned worktree" in content
    assert "at most one role run" in content


def test_goal_keeps_local_targets_local_until_promotion():
    content = command("goal.md")

    planning = "@.agents/commands/plan.md local:<lower-kebab-id> $2 --auto."
    implementation = "@.agents/commands/implement.md local:<lower-kebab-id> $2 --auto."
    review = "@.agents/commands/review.md local:<lower-kebab-id> --auto."
    promotion = "@.agents/commands/create-pr.md local:<lower-kebab-id> --auto."

    for phase in (planning, implementation, review, promotion):
        assert phase in content
    assert "preflight-goal.py local:<lower-kebab-id>" in content
    assert "confirm missing role configuration exactly as for remote goals" in content
    assert "resolve the Planner for `local:<lower-kebab-id>`" in content
    assert "resolve the Worker" in content
    assert "resolve the Reviewer" in content
    assert content.index(planning) < content.index(implementation)
    assert content.index(implementation) < content.index(review)
    assert content.index(review) < content.index(promotion)
    assert content.index("local_issue.record_promotion") < content.index(
        "@.agents/commands/create-pr.md OWNER/REPO#NUMBER --auto."
    )


def test_local_review_completes_before_promotion_without_a_pr():
    goal = command("goal.md")
    review = command("review.md")
    local_review = "@.agents/commands/review.md local:<lower-kebab-id> --auto."

    assert local_review in goal
    assert goal.index(local_review) < goal.index(
        "local_issue.py transition <lower-kebab-id> reviewed"
    ) < goal.index("@.agents/commands/create-pr.md local:<lower-kebab-id> --auto.")
    assert "For `local:<lower-kebab-id>`, validate the recorded local bundle" in review
    assert "Do not resolve a PR or use `_common-review-context.md`." in review


def test_local_target_promotes_before_entering_remote_delivery():
    plan = command("plan.md")
    create_pr = command("create-pr.md")

    local_plan = plan.split("For a remote target", 1)[0]
    assert "workflow_state.py" not in local_plan

    local_delivery = create_pr.split("For `single`", 1)[0]
    promotion = local_delivery.index("Promotion is the only remote mutation")
    mapping = local_delivery.index("local_issue.py promote <lower-kebab-id>")
    remote_state = local_delivery.index("initializes normal remote workflow state")
    delivery = local_delivery.index("git push")

    assert promotion < mapping < remote_state < delivery


def test_goal_contract_retries_only_environment_failures_and_blocks_decisions():
    content = command("goal.md")

    for text in (
        "record-environment-failure",
        "reset-environment-retry",
        "five consecutive identical",
        "scope expansion",
        "ambiguity",
        "security or permission gate",
        "conflict requiring human choice",
        "safe resume point",
        "non-mechanical",
        "invalid delegated evidence",
    ):
        assert text in content, text


def test_goal_contract_delivers_each_mechanical_cycle_and_readies_without_merging():
    content = command("goal.md")

    for text in (
        "until no OPEN findings remain",
        "fresh sibling",
        "PR delivery",
        "gh pr ready <pr-number> --repo OWNER/REPO",
        "isDraft",
        "false",
        "administrator-policy override",
    ):
        assert text in content, text

    assert content.index("pr ready <pr-number>") < content.index("pr merge <pr-number>")
    assert "--auto-merge" in content


def test_target_aware_contracts_acquire_the_source_worktree_from_primary():
    commands = (
        "plan.md",
        "implement.md",
        "goal.md",
        "create-pr.md",
        "begin-worktree.md",
    )

    for name in commands:
        content = command(name)
        assert "resolve-target-worktree.py" in content, name
        assert "primary checkout" in content, name
        assert "returned worktree" in content, name

    review_context = command("_common-review-context.md")
    assert "resolve-target-worktree.py" in review_context
    assert "primary checkout" in review_context
    assert "returned worktree" in review_context

    for name in ("review-fetch.md", "review-post.md", "review-refresh.md", "review-update.md"):
        assert "returned worktree" in command(name), name


def test_goal_delegates_implementation_pr_delivery_then_review():
    content = command("goal.md")

    assert "@.agents/commands/implement.md" in content
    assert "@.agents/commands/create-pr.md" in content
    assert "@.agents/commands/review.md" in content


def test_goal_directly_dispatches_each_delivery_phase_without_nested_delegation():
    goal = command("goal.md")
    implement = command("implement.md")

    for command_name in (
        "plan.md",
        "implement.md",
        "create-pr.md",
        "review.md",
        "review-implement.md",
        "review-validate.md",
    ):
        assert f"@.agents/commands/{command_name}" in goal, command_name

    assert "delegate `/plan`" not in implement
    assert "delegate `/create-pr`" not in implement


def test_begin_workflow_is_replaced_by_goal():
    assert not (COMMANDS / "begin-workflow.md").exists()


def test_command_readme_is_the_exact_public_inventory():
    public = {
        path.stem
        for path in COMMANDS.glob("*.md")
        if path.name != "README.md" and not path.name.startswith("_")
    }
    mapped = re.findall(r"^\| `/([^`]+)` \|", command("README.md"), re.MULTILINE)

    assert len(mapped) == len(set(mapped))
    assert set(mapped) == public


def test_removed_commands_are_not_referenced_in_guidance():
    removed = (
        "begin-workflow",
        "review-report",
        "review-loop",
        "review-clarify",
        "review-verify",
    )
    paths = [ROOT / "AGENTS.md", ROOT / "PROJECT-GUIDELINES.md"]
    paths += list((ROOT / ".agents").glob("**/*.md"))

    for path in paths:
        content = path.read_text(encoding="utf-8")
        for name in removed:
            assert f"/{name}" not in content, (path, name)
            assert f"commands/{name}.md" not in content, (path, name)


def test_branch_commands_have_frontmatter_and_share_common_modules():
    branch_commands = ("branch-breakdown.md", "branch-refresh.md", "branch-stack.md")
    common_modules = tuple(COMMANDS.glob("_common-branch-*.md"))

    for name in branch_commands:
        content = command(name)
        assert content.startswith("---\n")
        assert re.search(r"^description: \S", content, re.MULTILINE)
    for module in common_modules:
        consumers = [name for name in branch_commands if module.name in command(name)]
        assert len(consumers) >= 2, (module.name, consumers)


def test_documented_workflow_state_calls_match_required_cli_arguments():
    create_pr = command("create-pr.md")

    assert (
        "workflow_state.py set-pr OWNER/REPO#NUMBER <number> --url <url> --head <head> --base <base> --format json"
        in create_pr
    )


def test_commands_document_phase_sensitive_pr_delivery():
    create_pr = command("create-pr.md")
    goal = command("goal.md")

    assert (
        "workflow_state.py transition OWNER/REPO#NUMBER branched --status active --clear-pending-action --format json"
        in command("goal.md")
    )
    assert (
        "workflow_state.py set-artifacts OWNER/REPO#NUMBER --directory <directory> --spec <spec> --design <design> --plan <plan> --task <task> --format json"
        in command("plan.md")
    )
    assert (
        "workflow_state.py transition OWNER/REPO#NUMBER planned --status active --clear-pending-action --format json"
        in command("plan.md")
    )
    assert (
        "workflow_state.py transition OWNER/REPO#NUMBER implementing --status active --clear-pending-action --format json"
        in command("implement.md")
    )
    assert (
        "workflow_state.py transition OWNER/REPO#NUMBER implemented --status active --clear-pending-action --format json"
        in command("implement.md")
    )
    assert (
        "workflow_state.py transition OWNER/REPO#NUMBER pr_open --status active --clear-pending-action --format json"
        in create_pr
    )
    assert (
        "workflow_state.py transition OWNER/REPO#NUMBER reviewing --status active --clear-pending-action --format json"
        in create_pr
    )
    assert (
        "workflow_state.py transition OWNER/REPO#NUMBER reviewing --status active --clear-pending-action --format json"
        in goal
    )
    assert "preserve `reviewing`" in create_pr
    assert "preserves `reviewing`" in goal


def test_pr_updates_skip_unchanged_metadata_and_use_rest_for_changed_metadata():
    create_pr = command("create-pr.md")

    assert "skip the write when both are unchanged" in create_pr
    assert (
        "gh api --method PATCH repos/OWNER/REPO/pulls/<pr> --input "
        "./tmp/pr-metadata.json"
    ) in create_pr
    assert "gh pr edit" not in create_pr


def test_pr_claims_skip_existing_assignees_and_use_rest_when_missing():
    common = command("_common-github-ownership.md")

    assert "skip the write when `<login>` is already assigned" in common
    assert (
        "gh api --method POST repos/OWNER/REPO/issues/<number>/assignees "
        "--input ./tmp/assignees.json"
    ) in common
    assert "gh pr edit" not in common


def test_issue_creation_uses_native_cli_without_assignee():
    issue = command("issue.md")
    assert "gh issue create --repo OWNER/REPO" in issue
    assert "--assignee" not in issue


def test_ownership_contract_is_shared_by_github_workflows():
    module = "_common-github-ownership.md"
    consumers = ("goal.md", "implement.md", "create-pr.md")

    for name in consumers:
        content = command(name)
        assert module in content, name
        assert "_common-github-ownership.md" in content, name

    common = command(module)
    assert "preserve existing assignees" in common
    assert "authenticated login" in common
    assert "issue or PR" in common


def test_implement_claims_resolved_issue_and_pr_context_before_source_mutation():
    content = command("implement.md")

    claim = content.index("_common-github-ownership.md")
    transition = content.index("workflow_state.py transition")
    assert claim < transition
    assert "issue body" in content
    assert "PR body" in content


def test_goal_delegates_the_current_review_command():
    content = command("goal.md")

    assert "@.agents/commands/review.md" in content
    assert "review-report" not in content


def test_goal_records_review_evidence_before_delivery():
    content = command("goal.md")
    set_review = content.index("workflow_state.py set-review")
    delivered = content.index(
        "workflow_state.py transition OWNER/REPO#NUMBER goal_delivered"
    )

    assert set_review < delivered
    assert "<canonical-report>" in content
    assert "<canonical-archive>" in content
    assert "--state <ACTIVE_OPEN|COMPLETE|CLEAN|ARCHIVED>" in content


def test_goal_requires_independent_delegated_phase_ownership():
    content = command("goal.md")
    remote_goal = content.split("For remote targets, use the following phases:", 1)[1]

    required = (
        "orchestration-only",
        "fresh subagent A",
        "distinct fresh subagent B",
        "distinct fresh subagent C",
        "distinct fresh subagent D",
        "fresh subagent E",
        "directly resumes D by task identity",
        "fresh validator",
        "records the fallback",
        "fresh subagent F",
        "missing, failed, or malformed delegated result",
        "without advancing state",
        "parent-authored substitute work",
    )
    for text in required:
        assert text in content, text

    assert (
        remote_goal.index("fresh subagent A")
        < remote_goal.index("distinct fresh subagent B")
        < remote_goal.index("distinct fresh subagent C")
        < remote_goal.index("distinct fresh subagent D")
        < remote_goal.index("fresh subagent E")
        < remote_goal.index("directly resumes D by task identity")
        < remote_goal.index("fresh subagent F")
    )


def test_goal_requires_main_agent_sibling_dispatch_without_harness_dependencies():
    content = command("goal.md")

    required = (
        "Run `/goal` only in the main agent",
        "cannot establish that role",
        "directly dispatches sibling subagents",
        "directly dispatches fresh subagent A as a sibling",
        "directly dispatches distinct fresh subagent B as a sibling",
        "directly dispatches distinct fresh subagent C as a sibling",
        "directly dispatches distinct fresh subagent D as a sibling",
        "directly dispatching fresh subagent E as a sibling",
        "directly resumes D by task identity",
        "directly dispatches validation to a fresh validator sibling",
        "directly dispatches it to fresh subagent F as a sibling",
        "phase agents do not spawn agents",
        "nested-agent",
        "background-process",
        "polling",
        "harness-specific runner",
    )
    for text in required:
        assert text in content, text

    assert content.index("Run `/goal` only in the main agent") < content.index(
        "preflight-goal.py OWNER/REPO#NUMBER"
    )


def test_goal_contract_records_validated_per_goal_trace_events():
    content = command("goal.md")

    state_init = content.index("preflight-goal.py OWNER/REPO#NUMBER")
    trace_init = (
        "goal_trace.py init OWNER/REPO#NUMBER [--auto] [--commit] [--push] "
        "[--pr-create] [--pr-ready] [--merge] [--administrator-merge]"
    )
    pr_init = content.index("workflow_state.py init-pr OWNER/REPO!NUMBER")
    assert state_init < content.index(trace_init)
    assert pr_init < content.index(trace_init)
    assert content.count(trace_init) == 1

    for text in (
        "goal_trace.py validate OWNER/REPO#NUMBER",
        "goal_trace.py append-log OWNER/REPO#NUMBER",
        "goal_trace.py append-audit OWNER/REPO#NUMBER",
        "phase transitions",
        "delegation",
        "pause and resume",
        "block",
        "ready",
        "merge outcomes",
        "concise log",
        "detailed audit",
        "Never record secrets, raw command output",
        "Trace configuration is observability metadata, not authorization",
        "records current permission facts only and never grants permissions",
    ):
        assert text in content, text

    assert content.index("goal_trace.py validate OWNER/REPO#NUMBER") < content.index(
        "goal_trace.py append-log OWNER/REPO#NUMBER"
    )


def test_goal_role_routing_is_goal_only_and_evidence_gated():
    goal = command("goal.md")
    adaptation = ROOT / ".agents/skills/harness-adaptation/SKILL.md"

    for text in (
        "preflight-goal.py OWNER/REPO#NUMBER",
        ".agents/templates/goal-roles.default.json",
        ".agents/templates/goal-state.default.json",
        "goal_roles.py init <goal>",
        "--auto` still asks",
        "Planner: planning, final Specs synchronization, and PR delivery",
        "Worker: implementation and mechanical review remediation",
        "Reviewer: baseline review and review validation",
        "goal_roles.py resolve <goal>",
        "run_agent.py poll <run-id>",
        "run_agent.py fetch <run-id>",
        "run_agent.py stop <run-id>",
        "background mode when completion notifications are supported",
        "never use sleep plus repeated fetch",
        "monitor-loss error",
        "shell-tool timeout interrupts only the waiter",
        "validated `--goal`, `--role`, `--phase`, `--harness`, `--model`",
        "outstanding run ID",
        "native sibling delegation",
        "harness-adaptation",
        "canonical repository evidence",
        "run ID",
        "no raw harness output",
        "at most one role run",
        "For remote phases, resolve the configured role before every dispatch",
        "Before every baseline-review, remediation, validation, and remediation-delivery dispatch",
    ):
        assert text in goal, text

    assert adaptation.is_file()
    content = adaptation.read_text(encoding="utf-8")
    for text in (
        "opencode.md",
        "codex.md",
        "claude-code.md",
        "selected provider guide",
    ):
        assert text in content, text
    for provider in ("opencode.md", "codex.md", "claude-code.md"):
        guide = adaptation.parent / provider
        assert guide.is_file()
        provider_guide = guide.read_text(encoding="utf-8")
        assert "run_agent.py" in provider_guide
        assert "goal_roles.py verify <goal> <role>" in provider_guide
        assert "--goal <goal> --role <role> --phase <phase>" in provider_guide


def test_provider_guides_document_native_unattended_role_execution():
    guides = {
        "opencode.md": ("opencode run", "--auto", "--variant", "--session"),
        "codex.md": ("codex exec", "--sandbox", "workspace-write", "resume"),
        "claude-code.md": ("claude -p", "--permission-mode dontAsk", "--effort", "--resume"),
    }

    for name, required in guides.items():
        content = (ROOT / ".agents/skills/harness-adaptation" / name).read_text(
            encoding="utf-8"
        )
        for text in required:
            assert text in content, f"{name}: {text}"
        assert "run_agent.py <worktree>" in content
        assert "does not grant authorization" in content

    assert "dangerously-bypass-approvals-and-sandbox" in (
        ROOT / ".agents/skills/harness-adaptation/codex.md"
    ).read_text(encoding="utf-8")
    assert "--dangerously-skip-permissions" in (
        ROOT / ".agents/skills/harness-adaptation/claude-code.md"
    ).read_text(encoding="utf-8")
