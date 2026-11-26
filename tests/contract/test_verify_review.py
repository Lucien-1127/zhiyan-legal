from copy import deepcopy
from pathlib import Path
from urllib.error import HTTPError

import pytest
import yaml

from scripts.verify_review import (
    BRANCH,
    REPOSITORY,
    REVIEW_SCOPE,
    WORKFLOW,
    ReviewDecision,
    GitHub,
    InvalidEvidence,
    Invocation,
    evaluate,
    read_invocation,
)


BASE = "a" * 40
HEAD = "b" * 40
OLD = "c" * 40
BRANCH_PATH = f"refs/heads/{BRANCH}"
PATH = f"/repos/{REPOSITORY}"
PULL = f"{PATH}/pulls/20"
APPROVAL = {
    "id": 10,
    "state": "APPROVED",
    "commit_id": HEAD,
    "user": {"id": 20, "login": "independent", "type": "User"},
    "author_association": "COLLABORATOR",
    "body": "\n".join(f"## {area}\nChecked relevant source and evidence." for area in sorted(REVIEW_SCOPE)),
}


class EvidenceAPI:
    def __init__(self):
        self.pr = {
            "number": 20, "state": "open", "draft": False, "commits": 1,
            "head": {"sha": HEAD, "repo": {"full_name": REPOSITORY}},
            "base": {"sha": BASE, "ref": BRANCH, "repo": {"full_name": REPOSITORY}},
            "user": {"id": 1},
        }
        self.commits = [{"sha": HEAD, "author": {"id": 1}, "committer": {"id": 2}}]
        self.reviews = [deepcopy(APPROVAL)]
        self.checks = []
        self.statuses = []
        self.threads = []
        self.permission = {"user": {"id": 20}, "permission": "write"}
        self.queries = []
        self.changed_head = None
        self.review_reads = 0
        self.replace_reviews = None

    def get(self, path, body=None):
        self.queries.append(path)
        if path == PULL:
            result = deepcopy(self.pr)
            if self.changed_head and self.queries.count(PULL) > 1:
                result["head"]["sha"] = self.changed_head
            return result
        if path == f"{PATH}/compare/{BASE}...{self.pr['head']['sha']}":
            return {"merge_base_commit": {"sha": BASE}}
        if path == f"{PATH}/collaborators/independent/permission":
            return deepcopy(self.permission)
        if path == "/graphql":
            assert body["variables"] == {"owner": "Lucien-1127", "repo": "zhiyan-legal", "number": 20, "cursor": None}
            return {"data": {"repository": {"nameWithOwner": REPOSITORY, "pullRequest": {
                "number": 20,
                "headRefOid": self.pr["head"]["sha"],
                "baseRefOid": BASE,
                "reviewThreads": {
                    "nodes": deepcopy(self.threads),
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                },
            }}}}
        raise AssertionError(f"Unexpected endpoint {path}")

    def pages(self, path, key=None):
        self.queries.append(path)
        if path == f"{PULL}/reviews":
            self.review_reads += 1
            source = self.replace_reviews if self.review_reads > 1 and self.replace_reviews is not None else self.reviews
            return deepcopy(source)
        if path == f"{PULL}/commits":
            return deepcopy(self.commits)
        if path == f"{PATH}/commits/{self.pr['head']['sha']}/check-runs?filter=all":
            assert key == "check_runs"
            return deepcopy(self.checks)
        if path == f"{PATH}/commits/{self.pr['head']['sha']}/statuses":
            return deepcopy(self.statuses)
        raise AssertionError(f"Unexpected paginated endpoint {path}")


def run(api, invocation=None, allowed=None):
    return evaluate(api, invocation or Invocation(20, BASE), {20} if allowed is None else allowed)


def test_t01_independent_current_head_approval_passes():
    api = EvidenceAPI()
    result = run(api)
    assert (result.decision, result.head_sha, result.review_id) == (ReviewDecision.PASS, HEAD, 10)
    assert api.queries.count(PULL) == 2
    assert api.queries.count("/graphql") == 2


@pytest.mark.parametrize(
    "mutation", ["absent", "comment", "missing-scope", "no-allowlist", "hidden-comments", "hidden-html"],
)
def test_t02_missing_review_evidence_is_blocked(mutation):
    api = EvidenceAPI()
    allowed = {20}
    if mutation == "absent":
        api.reviews.clear()
    elif mutation == "comment":
        api.reviews[0]["state"] = "COMMENTED"
    elif mutation == "missing-scope":
        api.reviews[0]["body"] = "OK"
    elif mutation in {"hidden-comments", "hidden-html"}:
        placeholder = "<!-- hidden review placeholder -->" if mutation == "hidden-comments" else "<div hidden>hidden review placeholder</div>"
        api.reviews[0]["body"] = "\n".join(f"## {area}\n{placeholder}" for area in REVIEW_SCOPE)
    else:
        allowed.clear()
    assert run(api, allowed=allowed).decision is ReviewDecision.BLOCKED


def test_t03_old_approval_is_blocked():
    api = EvidenceAPI()
    api.reviews[0]["commit_id"] = OLD
    assert run(api).decision is ReviewDecision.BLOCKED


@pytest.mark.parametrize("evidence", ["unresolved-thread", "changes-requested"])
def test_t04_outstanding_review_findings_fail(evidence):
    api = EvidenceAPI()
    if evidence == "unresolved-thread":
        api.threads = [{"id": "thread", "isResolved": False}]
    else:
        api.reviews[0]["state"] = "CHANGES_REQUESTED"
    assert run(api).decision is ReviewDecision.FAIL


@pytest.mark.parametrize("status", [503, 403, 401], ids=["T05-unavailable", "T06-forbidden", "T06-unauthenticated"])
def test_api_failure_is_blocked(monkeypatch, status):
    api = GitHub("unit-test-token")
    error = HTTPError("https://api.github.com", status, "synthetic denial", {}, None)

    def unavailable(*args, **kwargs):
        raise error

    monkeypatch.setattr(api.opener, "open", unavailable)
    result = run(api)
    assert result.decision is ReviewDecision.BLOCKED
    assert "unit-test-token" not in result.reason


@pytest.mark.parametrize("case", ["author", "committer", "untrusted-user", "bot", "read-only", "wrong-permission-identity"])
def test_t07_untrusted_approval_fails(case):
    api = EvidenceAPI()
    wanted = 20
    if case == "author":
        api.pr["user"]["id"] = 20
    elif case == "committer":
        api.commits[0]["committer"]["id"] = 20
    elif case == "untrusted-user":
        wanted = 999
    elif case == "bot":
        api.reviews[0]["user"]["type"] = "Bot"
    elif case == "read-only":
        api.permission["permission"] = "read"
    else:
        api.permission["user"]["id"] = 999
    result = run(api, allowed={wanted})
    assert result.decision is ReviewDecision.FAIL
    assert result.review_id is None


def test_t08_push_or_dismissal_during_verification_blocks_approval():
    api = EvidenceAPI()
    api.changed_head = OLD
    assert run(api).decision is ReviewDecision.BLOCKED
    api = EvidenceAPI()
    api.replace_reviews = [{**APPROVAL, "state": "DISMISSED"}]
    assert run(api).decision is ReviewDecision.BLOCKED
    assert run(api, Invocation(20, BASE, OLD)).decision is ReviewDecision.BLOCKED


def test_t09_pr_branch_cannot_supply_workflow_or_event():
    env = {
        "GITHUB_REPOSITORY": REPOSITORY,
        "GITHUB_WORKFLOW_REF": f"{REPOSITORY}/{WORKFLOW}@{BRANCH_PATH}",
        "GITHUB_REF": BRANCH_PATH,
        "GITHUB_WORKFLOW_SHA": BASE,
        "GITHUB_EVENT_NAME": "pull_request_target",
    }
    event = {"repository": {"full_name": REPOSITORY}, "number": 20, "pull_request": {"head": {"sha": HEAD}}}
    assert read_invocation(env, event) == Invocation(20, BASE, HEAD)
    for changes in [
        {"GITHUB_WORKFLOW_REF": f"{REPOSITORY}/{WORKFLOW}@refs/pull/20/merge"},
        {"GITHUB_REF": "refs/heads/codex/citation-integrity"},
        {"GITHUB_EVENT_NAME": "pull_request"},
        {"GITHUB_REPOSITORY": "untrusted/repo"},
    ]:
        with pytest.raises(InvalidEvidence):
            read_invocation({**env, **changes}, event)


def test_t09_workflow_has_no_write_token_and_checks_out_only_trusted_sha():
    workflow = yaml.load(Path(WORKFLOW).read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert set(workflow["on"]) == {"pull_request_target", "issue_comment", "workflow_dispatch"}
    assert workflow["permissions"] == {}
    job = workflow["jobs"]["verify"]
    assert job["name"] != "review"
    assert set(job["permissions"].values()) == {"read"}
    checkout = job["steps"][0]
    assert checkout["uses"].split("@")[0] == "actions/checkout"
    assert len(checkout["uses"].split("@")[1]) == 40
    assert checkout["with"] == {"ref": "${{ github.workflow_sha }}", "persist-credentials": "false"}


def test_t10_green_test_matrix_does_not_replace_review():
    api = EvidenceAPI()
    api.reviews.clear()
    api.checks = [{"name": name, "conclusion": "success"} for name in
                  ("test (3.10)", "test (3.11)", "test (3.12)", "frontend")]
    assert run(api).decision is ReviewDecision.BLOCKED


@pytest.mark.parametrize("source", ["check-run", "commit-status", "both"])
def test_t11_same_name_without_authenticated_publisher_fails(source):
    api = EvidenceAPI()
    if source in {"check-run", "both"}:
        api.checks = [{"name": "review", "conclusion": "success"}]
    if source in {"commit-status", "both"}:
        api.statuses = [{"context": "Review", "state": "success"}]
    assert run(api).decision is ReviewDecision.FAIL



def test_t11_same_name_status_appearing_during_verification_fails(monkeypatch):
    api = EvidenceAPI()
    read_pages = api.pages

    def add_status_after_review(path, key=None):
        rows = read_pages(path, key)
        if path == f"{PULL}/reviews":
            api.statuses = [{"context": "review", "state": "success"}]
        return rows

    monkeypatch.setattr(api, "pages", add_status_after_review)
    assert run(api).decision is ReviewDecision.FAIL
