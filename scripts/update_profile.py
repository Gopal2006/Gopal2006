#!/usr/bin/env python3
"""Refresh GitHub-profile README sections using only public GitHub data.

No third-party dependencies are required. The updater changes the README only
when a generated section changes; the scheduled workflow therefore won't add
an empty profile commit every day.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

USERNAME = "Gopal2006"
API_ROOT = "https://api.github.com"
README_PATH = Path(__file__).resolve().parents[1] / "README.md"
API_VERSION = "2022-11-28"
TIMEOUT_SECONDS = 20

SECTION_NAMES = ("ACTIVITY", "PRS", "STATS", "UPDATED")


class GitHubAPIError(RuntimeError):
    """Raised when GitHub data cannot be fetched safely."""


def request_json(url: str) -> object:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": f"{USERNAME}-profile-readme-updater",
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise GitHubAPIError(f"Could not fetch GitHub data from {url}: {exc}") from exc


def get_json(path_or_url: str) -> object:
    url = path_or_url if path_or_url.startswith("https://api.github.com/") else f"{API_ROOT}{path_or_url}"
    return request_json(url)


def get_public_owned_repositories() -> list[dict]:
    repos: list[dict] = []
    page = 1
    while True:
        query = urlencode({"type": "owner", "per_page": 100, "page": page, "sort": "updated"})
        batch = get_json(f"/users/{USERNAME}/repos?{query}")
        if not isinstance(batch, list):
            raise GitHubAPIError("Unexpected response while retrieving public repositories.")
        public_batch = [repo for repo in batch if isinstance(repo, dict) and repo.get("private") is False]
        repos.extend(public_batch)
        if len(batch) < 100:
            break
        page += 1
    return repos


def escape_markdown(value: object, max_length: int = 160) -> str:
    """Keep API-provided titles from breaking generated Markdown structure."""
    text = " ".join(str(value or "").split())
    text = (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("|", "&#124;")
                .replace("[", "&#91;")
                .replace("]", "&#93;")
                .replace("`", "&#96;"))
    return text[:max_length] + ("…" if len(text) > max_length else "")


def short_date(value: str) -> str:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%b %d")
    except (ValueError, TypeError):
        return "recently"


def activity_line(event: dict) -> str | None:
    kind = event.get("type", "")
    payload = event.get("payload") or {}
    repo_name = (event.get("repo") or {}).get("name", "")
    created = short_date(event.get("created_at", ""))
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo_name):
        return None

    repo_link = f"https://github.com/{repo_name}"
    repo_label = f"[{escape_markdown(repo_name, 100)}]({repo_link})"

    if kind == "PushEvent":
        branch = str(payload.get("ref", "")).removeprefix("refs/heads/")
        commits_url = f"{repo_link}/commits/{quote(branch, safe='/')}" if branch else f"{repo_link}/commits"
        size = payload.get("size")
        count = size if isinstance(size, int) and size > 0 else len(payload.get("commits") or [])
        change_label = f"pushed {count} commit{'s' if count != 1 else ''}" if count else "pushed updates"
        return f"- **Push** · {repo_label} — [{change_label}]({commits_url}) · {created}"

    if kind == "PullRequestEvent":
        pull = payload.get("pull_request") or {}
        number = pull.get("number") or payload.get("number")
        if not number:
            return None
        title = escape_markdown(pull.get("title", "Pull request"))
        action = payload.get("action", "updated")
        action_text = {"opened": "opened", "reopened": "reopened", "synchronize": "updated", "closed": "closed", "ready_for_review": "marked ready"}.get(action, "updated")
        return f"- **Pull request** · [{title}](https://github.com/{repo_name}/pull/{number}) in {repo_label} — {action_text} · {created}"

    if kind == "PullRequestReviewEvent":
        pull = payload.get("pull_request") or {}
        number = pull.get("number")
        if not number:
            return None
        return f"- **Review** · [PR #{number}]({repo_link}/pull/{number}) in {repo_label} · {created}"

    if kind == "IssuesEvent":
        issue = payload.get("issue") or {}
        number = issue.get("number")
        if not number:
            return None
        action = payload.get("action", "updated")
        action_text = {"opened": "opened", "reopened": "reopened", "closed": "closed", "assigned": "updated"}.get(action, "updated")
        title = escape_markdown(issue.get("title", "Issue"))
        return f"- **Issue** · [{title}]({repo_link}/issues/{number}) in {repo_label} — {action_text} · {created}"

    if kind == "IssueCommentEvent":
        issue = payload.get("issue") or {}
        number = issue.get("number")
        if not number:
            return None
        target_type = "pull" if issue.get("pull_request") else "issues"
        target = "PR" if target_type == "pull" else "issue"
        title = escape_markdown(issue.get("title", target.title()))
        return f"- **Comment** · [{title}]({repo_link}/{target_type}/{number}) in {repo_label} ({target}) · {created}"

    if kind == "CreateEvent":
        ref_type = payload.get("ref_type", "branch")
        ref = payload.get("ref")
        if ref_type == "repository":
            return f"- **Repository** · created {repo_label} · {created}"
        if ref:
            url = f"{repo_link}/tree/{quote(str(ref), safe='/')}"
            return f"- **{escape_markdown(ref_type.title(), 30)}** · created [`{escape_markdown(ref, 80)}`]({url}) in {repo_label} · {created}"

    if kind == "ReleaseEvent":
        release = payload.get("release") or {}
        tag = str(release.get("tag_name", ""))
        url = f"{repo_link}/releases/tag/{quote(tag, safe='')}" if tag else f"{repo_link}/releases"
        label = escape_markdown(tag or "release", 80)
        return f"- **Release** · [{label}]({url}) in {repo_label} · {created}"

    return None


def render_activity(events: list[dict]) -> str:
    lines: list[str] = []
    seen: set[str] = set()
    for event in events:
        line = activity_line(event)
        if line and line not in seen:
            seen.add(line)
            lines.append(line)
        if len(lines) >= 5:
            break
    if not lines:
        return "_No recent public events were available from GitHub's recent activity feed at the last refresh._"
    return "\n".join(lines)


def collect_public_prs() -> list[dict]:
    query = urlencode({"q": f"author:{USERNAME} is:pr", "sort": "updated", "order": "desc", "per_page": 8})
    search = get_json(f"/search/issues?{query}")
    if not isinstance(search, dict):
        raise GitHubAPIError("Unexpected response while retrieving pull requests.")

    collected: list[dict] = []
    for item in search.get("items", []):
        if not isinstance(item, dict) or not item.get("number"):
            continue
        repository_url = str(item.get("repository_url", ""))
        match = re.fullmatch(r"https://api\.github\.com/repos/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)", repository_url)
        if not match:
            continue
        repo_name = match.group(1)
        details_url = f"{API_ROOT}/repos/{repo_name}/pulls/{item['number']}"
        try:
            details = get_json(details_url)
        except GitHubAPIError:
            # Skip unverifiable entries rather than risk exposing non-public metadata.
            continue
        base_repo = ((details.get("base") or {}).get("repo") or {}) if isinstance(details, dict) else {}
        if base_repo.get("private") is not False:
            continue
        merged_at = details.get("merged_at")
        if merged_at:
            status = "merged"
        elif details.get("state") == "open":
            status = "open"
        else:
            status = "closed"
        collected.append({
            "title": escape_markdown(item.get("title", "Pull request")),
            "url": f"https://github.com/{repo_name}/pull/{item['number']}",
            "repo": escape_markdown(repo_name, 100),
            "repo_url": f"https://github.com/{repo_name}",
            "number": item["number"],
            "status": status,
            "updated_at": item.get("updated_at", ""),
        })
    return collected[:5]


def render_prs(prs: list[dict]) -> str:
    if not prs:
        return "_No public pull requests were found by the GitHub API at the last refresh. This section updates automatically as public PRs become available._"
    rows = ["| Pull request | Repository | Status |", "|---|---|---|"]
    for pr in prs:
        status = pr.get("status", "closed").capitalize()
        rows.append(f"| [#{pr['number']} · {pr['title']}]({pr['url']}) | [{pr['repo']}]({pr['repo_url']}) | `{status}` |")
    return "\n".join(rows)


def render_stats(profile: dict, repos: list[dict]) -> str:
    public_repos = profile.get("public_repos", len(repos))
    followers = profile.get("followers", 0)
    stars = sum(int(repo.get("stargazers_count", 0) or 0) for repo in repos)
    created_at = str(profile.get("created_at", ""))
    account_since = created_at[:4] if re.fullmatch(r"\d{4}-\d{2}-\d{2}T.*", created_at) else "—"
    return "\n".join([
        '<table align="center">',
        '  <tr>',
        f'    <td align="center"><strong>Public repositories</strong><br />{public_repos}</td>',
        f'    <td align="center"><strong>Followers</strong><br />{followers}</td>',
        f'    <td align="center"><strong>Stars on personal public repos</strong><br />{stars}</td>',
        f'    <td align="center"><strong>GitHub since</strong><br />{account_since}</td>',
        '  </tr>',
        '</table>',
        '<p align="center"><sub>Public profile data only; stars count repositories owned by this account.</sub></p>',
    ])


def marker(name: str, boundary: str) -> str:
    return f"<!-- PROFILE:{boundary}:{name} -->"


def extract_section(text: str, name: str) -> str:
    start = marker(name, "START")
    end = marker(name, "END")
    match = re.search(re.escape(start) + r"\s*(.*?)\s*" + re.escape(end), text, re.DOTALL)
    if not match:
        raise ValueError(f"Missing or malformed {name} markers in README.md")
    return match.group(1).strip()


def replace_section(text: str, name: str, new_content: str) -> str:
    start = marker(name, "START")
    end = marker(name, "END")
    pattern = re.escape(start) + r".*?" + re.escape(end)
    replacement = f"{start}\n{new_content}\n{end}"
    updated, count = re.subn(pattern, lambda _: replacement, text, count=1, flags=re.DOTALL)
    if count != 1:
        raise ValueError(f"Missing or malformed {name} markers in README.md")
    return updated


def main() -> int:
    if not README_PATH.exists():
        print(f"README not found: {README_PATH}", file=sys.stderr)
        return 1
    try:
        original = README_PATH.read_text(encoding="utf-8")
        profile = get_json(f"/users/{USERNAME}")
        if not isinstance(profile, dict):
            raise GitHubAPIError("Unexpected user-profile response.")
        repos = get_public_owned_repositories()
        events = get_json(f"/users/{USERNAME}/events/public?per_page=100")
        if not isinstance(events, list):
            raise GitHubAPIError("Unexpected response while retrieving public activity.")
        prs = collect_public_prs()

        updated = original
        updated = replace_section(updated, "ACTIVITY", render_activity(events))
        updated = replace_section(updated, "PRS", render_prs(prs))
        updated = replace_section(updated, "STATS", render_stats(profile, repos))

        data_changed = any(extract_section(original, name) != extract_section(updated, name)
                           for name in ("ACTIVITY", "PRS", "STATS"))
        if data_changed:
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            updated = replace_section(updated, "UPDATED", f"_Last data update: {now}_")

        if updated != original:
            README_PATH.write_text(updated.rstrip() + "\n", encoding="utf-8")
            print("Profile README generated sections updated.")
        else:
            print("Profile README is already current; no write needed.")
        return 0
    except (GitHubAPIError, ValueError, OSError) as exc:
        print(f"Profile refresh failed without changing the README: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
