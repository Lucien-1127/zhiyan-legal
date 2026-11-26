"""Verify independent GitHub review evidence for the latest pull request head."""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener


REPOSITORY = "Lucien-1127/zhiyan-legal"
WORKFLOW = ".github/workflows/verify-review-evidence.yml"
BRANCH = "main"
SHA = re.compile(r"[0-9a-f]{40}")
REVIEW_STATES = {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}
REVIEW_SCOPE = {"程式邏輯", "安全漏洞", "回歸風險", "測試覆蓋", "架構一致性", "Review Threads"}
THREAD_QUERY = """
query($owner: String!, $repo: String!, $number: Int!, $cursor: String) {
  repository(owner: $owner, name: $repo) {
    nameWithOwner
    pullRequest(number: $number) {
      number
      headRefOid
      baseRefOid
      reviewThreads(first: 100, after: $cursor) {
        nodes { id isResolved }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}
"""


class ReviewDecision(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class Result:
    decision: ReviewDecision
    reason: str
    head_sha: str | None = None
    review_id: int | None = None


@dataclass(frozen=True)
class Invocation:
    number: int
    workflow_sha: str
    event_head: str | None = None


class MissingEvidence(Exception):
    """The verifier cannot establish the required state."""


class InvalidEvidence(Exception):
    """The evidence conflicts with the trusted invocation or review policy."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise URLError("Unexpected GitHub redirect")


class GitHub:
    def __init__(self, token: str):
        if not token:
            raise MissingEvidence("GitHub API token is unavailable")
        self.token = token
        self.opener = build_opener(NoRedirect())

    def get(self, path: str, body: dict | None = None) -> Any:
        request = Request(
            f"https://api.github.com{path}",
            data=json.dumps(body).encode() if body is not None else None,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "Content-Type": "application/json",
                "User-Agent": "zhiyan-review-evidence",
            },
        )
        try:
            with self.opener.open(request, timeout=20) as response:
                return json.load(response)
        except (OSError, ValueError) as exc:
            raise MissingEvidence("GitHub API unavailable, unauthorized or invalid") from exc

    def pages(self, path: str, key: str | None = None) -> list[dict]:
        separator = "&" if "?" in path else "?"
        rows = []
        for page in range(1, 11):
            result = self.get(f"{path}{separator}per_page=100&page={page}")
            batch = result if key is None else result[key]
            if not isinstance(batch, list) or len(batch) > 100:
                raise MissingEvidence("Invalid GitHub pagination")
            rows.extend(batch)
            if len(batch) < 100:
                if key and result["total_count"] != len(rows):
                    raise MissingEvidence("GitHub returned incomplete check runs")
                return rows
        raise MissingEvidence("GitHub pagination exceeded the verification limit")


def read_invocation(env: dict, event: dict) -> Invocation:
    expected_ref = f"{REPOSITORY}/{WORKFLOW}@refs/heads/{BRANCH}"
    if (
        env.get("GITHUB_REPOSITORY") != REPOSITORY
        or env.get("GITHUB_WORKFLOW_REF") != expected_ref
        or env.get("GITHUB_REF") != f"refs/heads/{BRANCH}"
        or event.get("repository", {}).get("full_name") != REPOSITORY
    ):
        raise InvalidEvidence("Workflow or event did not originate from the trusted repository ref")

    workflow_sha = env.get("GITHUB_WORKFLOW_SHA", "")
    if not SHA.fullmatch(workflow_sha):
        raise InvalidEvidence("Invalid trusted workflow SHA")

    event_name = env.get("GITHUB_EVENT_NAME")
    event_head = None
    if event_name == "pull_request_target":
        number = event["number"]
        event_head = event["pull_request"]["head"]["sha"]
        if not SHA.fullmatch(event_head):
            raise InvalidEvidence("Invalid event head SHA")
    elif event_name == "issue_comment":
        issue, comment = event["issue"], event["comment"]
        if (
            "pull_request" not in issue
            or comment["body"].strip() != "/verify-review"
            or comment["author_association"] not in {"OWNER", "MEMBER", "COLLABORATOR"}
        ):
            raise InvalidEvidence("The review verification command is not authorized")
        number = issue["number"]
    elif event_name == "workflow_dispatch":
        input_number = str(event["inputs"]["pull_request"])
        if not re.fullmatch(r"[1-9][0-9]*", input_number):
            raise InvalidEvidence("Invalid dispatch pull request number")
        number = int(input_number)
    else:
        raise InvalidEvidence("Untrusted workflow event")
    if type(number) is not int or number < 1:
        raise InvalidEvidence("Invalid pull request number")
    return Invocation(number, workflow_sha, event_head)


def approved_scope(body: str) -> bool:
    """Require the independent reviewer to record evidence in each review area."""
    visible_body = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    if re.search(r"</?[A-Za-z][^>\n]*>", visible_body):
        return False
    sections: dict[str, list[str]] = {}
    current = None
    for line in visible_body.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            if current in sections:
                return False
            sections[current] = []
        elif current and line.strip():
            sections[current].append(line.strip())
    return all(re.search(r"[^\W_]", " ".join(sections.get(name, []))) for name in REVIEW_SCOPE)


def read_threads(api: GitHub, number: int, head: str, base: str) -> list[dict]:
    owner, repo = REPOSITORY.split("/")
    cursor = None
    threads = []
    for _ in range(10):
        result = api.get("/graphql", {
            "query": THREAD_QUERY,
            "variables": {"owner": owner, "repo": repo, "number": number, "cursor": cursor},
        })
        if result.get("errors"):
            raise MissingEvidence("GitHub review threads are unavailable")
        repository = result["data"]["repository"]
        pull = repository["pullRequest"]
        if repository["nameWithOwner"] != REPOSITORY or pull["number"] != number:
            raise InvalidEvidence("Review threads refer to another pull request")
        if pull["headRefOid"] != head or pull["baseRefOid"] != base:
            raise MissingEvidence("The PR changed while reading review threads")
        data = pull["reviewThreads"]
        threads.extend(data["nodes"])
        page = data["pageInfo"]
        if page["hasNextPage"] is False:
            return threads
        if not page["endCursor"] or page["endCursor"] == cursor:
            break
        cursor = page["endCursor"]
    raise MissingEvidence("Review thread pagination is incomplete")


def check_review_context(api: GitHub, commits_path: str) -> None:
    for endpoint, name, key in (("check-runs?filter=all", "name", "check_runs"), ("statuses", "context", None)):
        rows = api.pages(f"{commits_path}/{endpoint}", key)
        if any(row[name].casefold() == "review" for row in rows):
            raise InvalidEvidence("A same-name review status exists without an approved publisher binding")


def evaluate(api: GitHub, invocation: Invocation, allowed_reviewers: set[int]) -> Result:
    repository_path = f"/repos/{REPOSITORY}"
    pull_path = f"{repository_path}/pulls/{invocation.number}"
    head = None
    try:
        pull = api.get(pull_path)
        if (
            pull["number"] != invocation.number
            or pull["base"]["repo"]["full_name"] != REPOSITORY
            or pull["base"]["ref"] != BRANCH
        ):
            raise InvalidEvidence("The PR does not target the trusted repository and branch")
        candidate_head, base = pull["head"]["sha"], pull["base"]["sha"]
        if not SHA.fullmatch(candidate_head) or not SHA.fullmatch(base):
            raise InvalidEvidence("Invalid head or base SHA returned by GitHub")
        head = candidate_head
        if (
            pull["state"] != "open"
            or pull["draft"]
            or pull["head"]["repo"]["full_name"] != REPOSITORY
        ):
            raise MissingEvidence("Only open, same-repository, non-draft pull requests are eligible")
        if invocation.event_head is not None and invocation.event_head != head:
            raise MissingEvidence("A new head superseded the event")
        if invocation.workflow_sha != base:
            raise MissingEvidence("Trusted workflow SHA and current PR base differ")
        comparison = api.get(f"{repository_path}/compare/{base}...{head}")
        if comparison["merge_base_commit"]["sha"] != base:
            raise MissingEvidence("The PR head does not contain the current base")

        commit_count = pull["commits"]
        if not 0 < commit_count <= 250:
            raise MissingEvidence("Cannot establish the complete PR contributor list")
        commits = api.pages(f"{pull_path}/commits")
        if len(commits) != commit_count or commits[-1]["sha"] != head:
            raise MissingEvidence("PR contributor list is incomplete or stale")
        author = pull["user"]["id"]
        if type(author) is not int or author < 1:
            raise MissingEvidence("The PR author has no verifiable GitHub identity")
        contributors = {author}
        for commit in commits:
            for role in ("author", "committer"):
                identity = commit.get(role)
                if not identity or type(identity["id"]) is not int:
                    raise MissingEvidence("A PR commit contributor has no verifiable GitHub identity")
                contributors.add(identity["id"])

        commits_path = f"{repository_path}/commits/{head}"
        check_review_context(api, commits_path)

        if any(thread["isResolved"] is not True for thread in read_threads(api, invocation.number, head, base)):
            raise InvalidEvidence("An unresolved GitHub review thread remains")

        reviews = api.pages(f"{pull_path}/reviews")
        latest = {}
        for review in sorted(reviews, key=lambda row: row["id"]):
            if review["state"] in REVIEW_STATES:
                latest[review["user"]["id"]] = review
        for identity, review in latest.items():
            if review["state"] == "CHANGES_REQUESTED" and review["author_association"] in {"OWNER", "MEMBER", "COLLABORATOR"}:
                raise InvalidEvidence("An authorized contributor has requested changes")
            if review["state"] == "APPROVED" and identity in contributors:
                raise InvalidEvidence("Approval came from the PR author or a commit contributor")
        if not allowed_reviewers:
            raise MissingEvidence("Trusted independent reviewer IDs have not been configured")

        for identity, review in latest.items():
            if review["state"] != "APPROVED" or review["commit_id"] != head:
                continue
            if identity not in allowed_reviewers:
                raise InvalidEvidence("Approval came from outside the trusted reviewer list")
            reviewer = review["user"]
            if reviewer["type"] != "User":
                raise InvalidEvidence("Approval did not come from an independent human reviewer")
            permission = api.get(f"{repository_path}/collaborators/{quote(reviewer['login'], safe='')}/permission")
            if permission["user"]["id"] != identity or permission["permission"] not in {"admin", "maintain", "write"}:
                raise InvalidEvidence("Reviewer does not have the required repository permission")
            if not approved_scope(review.get("body") or ""):
                continue
            current = api.get(pull_path)
            if (
                current["number"] != invocation.number
                or current["head"]["sha"] != head
                or current["head"]["repo"]["full_name"] != REPOSITORY
                or current["base"]["sha"] != base
                or current["base"]["ref"] != BRANCH
                or current["base"]["repo"]["full_name"] != REPOSITORY
                or current["state"] != "open"
                or current["draft"]
            ):
                raise MissingEvidence("The PR changed during verification")
            if api.pages(f"{pull_path}/reviews") != reviews:
                raise MissingEvidence("Reviews changed during verification")
            if any(thread["isResolved"] is not True for thread in read_threads(api, invocation.number, head, base)):
                raise InvalidEvidence("An unresolved GitHub review thread remains")
            check_review_context(api, commits_path)
            return Result(ReviewDecision.PASS, "Independent approval includes current-head review evidence", head, review["id"])
        raise MissingEvidence("No complete independent approval for the current head")
    except InvalidEvidence as exc:
        return Result(ReviewDecision.FAIL, str(exc), head)
    except MissingEvidence as exc:
        return Result(ReviewDecision.BLOCKED, str(exc), head)
    except (KeyError, ValueError, TypeError, AttributeError, IndexError):
        return Result(ReviewDecision.BLOCKED, "GitHub response was incomplete or malformed", head)


def main() -> int:
    try:
        event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
        invocation = read_invocation(dict(os.environ), event)
        reviewer_ids = {int(value) for value in os.environ.get("INDEPENDENT_REVIEWER_IDS", "").split()}
        result = evaluate(GitHub(os.environ.get("GH_TOKEN", "")), invocation, reviewer_ids)
    except InvalidEvidence as exc:
        result = Result(ReviewDecision.FAIL, str(exc))
    except (MissingEvidence, OSError, KeyError, ValueError, TypeError, AttributeError):
        result = Result(ReviewDecision.BLOCKED, "Trusted invocation or GitHub credentials are incomplete")
    print(json.dumps(asdict(result)))
    return {ReviewDecision.PASS: 0, ReviewDecision.FAIL: 1, ReviewDecision.BLOCKED: 2}[result.decision]


if __name__ == "__main__":
    raise SystemExit(main())
