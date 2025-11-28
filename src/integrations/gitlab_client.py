"""GitLab API client for fetching team activity."""

import httpx
from datetime import datetime, date, timedelta
from typing import Optional


class GitLabClient:
    """Client for interacting with GitLab API."""

    def __init__(self, url: str, token: str, project_ids: Optional[list[int]] = None):
        """
        Initialize GitLab client.

        Args:
            url: GitLab instance URL (e.g., https://gitlab.example.com)
            token: Personal access token
            project_ids: Specific project IDs to track, None = all accessible
        """
        self.url = url.rstrip("/")
        self.token = token
        self.project_ids = project_ids
        self.headers = {
            "PRIVATE-TOKEN": token,
            "Content-Type": "application/json"
        }

    async def get_user_activity(
        self,
        username: str,
        start_date: date,
        end_date: date
    ) -> dict:
        """
        Get user's activity for a specific date range.

        Args:
            username: GitLab username
            start_date: Start date
            end_date: End date

        Returns:
            Dictionary with activity summary
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Get user ID
            user_id = await self._get_user_id(client, username)
            if not user_id:
                return {
                    "error": f"User {username} not found",
                    "commits": [],
                    "merge_requests": [],
                    "issues": []
                }

            # Get commits
            commits = await self._get_user_commits(client, user_id, start_date, end_date)

            # Get merge requests
            merge_requests = await self._get_user_merge_requests(client, user_id, start_date, end_date)

            # Get issues
            issues = await self._get_user_issues(client, user_id, start_date, end_date)

            return {
                "username": username,
                "commits": commits,
                "merge_requests": merge_requests,
                "issues": issues,
                "summary": {
                    "total_commits": len(commits),
                    "total_merge_requests": len(merge_requests),
                    "total_issues": len(issues)
                }
            }

    async def _get_user_id(self, client: httpx.AsyncClient, username: str) -> Optional[int]:
        """Get user ID from username."""
        try:
            response = await client.get(
                f"{self.url}/api/v4/users",
                headers=self.headers,
                params={"username": username}
            )
            response.raise_for_status()
            users = response.json()
            if users:
                return users[0]["id"]
        except Exception as e:
            print(f"Error getting user ID: {e}")
        return None

    async def _get_user_commits(
        self,
        client: httpx.AsyncClient,
        user_id: int,
        start_date: date,
        end_date: date
    ) -> list[dict]:
        """Get user's commits in the date range."""
        commits = []
        projects = self.project_ids or await self._get_all_project_ids(client)

        for project_id in projects:
            try:
                response = await client.get(
                    f"{self.url}/api/v4/projects/{project_id}/repository/commits",
                    headers=self.headers,
                    params={
                        "since": start_date.isoformat(),
                        "until": (end_date + timedelta(days=1)).isoformat(),
                        "author_id": user_id,
                        "per_page": 100
                    }
                )
                response.raise_for_status()
                project_commits = response.json()

                for commit in project_commits:
                    commits.append({
                        "project_id": project_id,
                        "sha": commit["id"][:8],
                        "title": commit["title"],
                        "message": commit["message"],
                        "created_at": commit["created_at"],
                        "web_url": commit["web_url"]
                    })
            except Exception as e:
                print(f"Error getting commits for project {project_id}: {e}")

        return commits

    async def _get_user_merge_requests(
        self,
        client: httpx.AsyncClient,
        user_id: int,
        start_date: date,
        end_date: date
    ) -> list[dict]:
        """Get user's merge requests in the date range."""
        merge_requests = []

        try:
            response = await client.get(
                f"{self.url}/api/v4/merge_requests",
                headers=self.headers,
                params={
                    "author_id": user_id,
                    "created_after": start_date.isoformat(),
                    "created_before": (end_date + timedelta(days=1)).isoformat(),
                    "scope": "all",
                    "per_page": 100
                }
            )
            response.raise_for_status()
            mrs = response.json()

            for mr in mrs:
                # Filter by project IDs if specified
                if self.project_ids and mr["project_id"] not in self.project_ids:
                    continue

                merge_requests.append({
                    "project_id": mr["project_id"],
                    "iid": mr["iid"],
                    "title": mr["title"],
                    "state": mr["state"],
                    "created_at": mr["created_at"],
                    "merged_at": mr.get("merged_at"),
                    "web_url": mr["web_url"]
                })
        except Exception as e:
            print(f"Error getting merge requests: {e}")

        return merge_requests

    async def _get_user_issues(
        self,
        client: httpx.AsyncClient,
        user_id: int,
        start_date: date,
        end_date: date
    ) -> list[dict]:
        """Get issues assigned to user or created by user in the date range."""
        issues = []

        try:
            # Get issues assigned to user
            response = await client.get(
                f"{self.url}/api/v4/issues",
                headers=self.headers,
                params={
                    "assignee_id": user_id,
                    "scope": "all",
                    "per_page": 100
                }
            )
            response.raise_for_status()
            assigned_issues = response.json()

            for issue in assigned_issues:
                # Filter by project IDs if specified
                if self.project_ids and issue["project_id"] not in self.project_ids:
                    continue

                # Filter by date range
                created = datetime.fromisoformat(issue["created_at"].replace("Z", "+00:00"))
                if start_date <= created.date() <= end_date:
                    issues.append({
                        "project_id": issue["project_id"],
                        "iid": issue["iid"],
                        "title": issue["title"],
                        "state": issue["state"],
                        "created_at": issue["created_at"],
                        "closed_at": issue.get("closed_at"),
                        "web_url": issue["web_url"]
                    })
        except Exception as e:
            print(f"Error getting issues: {e}")

        return issues

    async def _get_all_project_ids(self, client: httpx.AsyncClient) -> list[int]:
        """Get all accessible project IDs."""
        try:
            response = await client.get(
                f"{self.url}/api/v4/projects",
                headers=self.headers,
                params={"membership": True, "per_page": 100}
            )
            response.raise_for_status()
            projects = response.json()
            return [p["id"] for p in projects]
        except Exception as e:
            print(f"Error getting projects: {e}")
            return []

    async def get_issue_details(self, project_id: int, issue_iid: int) -> Optional[dict]:
        """
        Get detailed information about a specific issue.

        Args:
            project_id: Project ID
            issue_iid: Issue IID (internal ID)

        Returns:
            Issue details or None if not found
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.url}/api/v4/projects/{project_id}/issues/{issue_iid}",
                    headers=self.headers
                )
                response.raise_for_status()
                issue = response.json()

                return {
                    "title": issue["title"],
                    "description": issue["description"],
                    "state": issue["state"],
                    "created_at": issue["created_at"],
                    "updated_at": issue["updated_at"],
                    "closed_at": issue.get("closed_at"),
                    "labels": issue.get("labels", []),
                    "assignees": [a["name"] for a in issue.get("assignees", [])],
                    "web_url": issue["web_url"]
                }
            except Exception as e:
                print(f"Error getting issue details: {e}")
                return None