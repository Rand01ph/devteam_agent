"""Jira API client for fetching team activity."""

import httpx
import base64
from datetime import datetime, date, timedelta
from typing import Optional


class JiraClient:
    """Client for interacting with Jira API."""

    def __init__(self, url: str, username: str, api_token: str, project_keys: Optional[list[str]] = None):
        """
        Initialize Jira client.

        Args:
            url: Jira instance URL (e.g., https://jira.example.com)
            username: Jira username/email
            api_token: API token
            project_keys: Specific project keys to track, None = all accessible
        """
        self.url = url.rstrip("/")
        self.username = username
        self.api_token = api_token
        self.project_keys = project_keys

        # Basic auth header
        auth_str = f"{username}:{api_token}"
        auth_bytes = auth_str.encode("ascii")
        auth_b64 = base64.b64encode(auth_bytes).decode("ascii")

        self.headers = {
            "Authorization": f"Basic {auth_b64}",
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
            username: Jira username/email
            start_date: Start date
            end_date: End date

        Returns:
            Dictionary with activity summary
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Get issues assigned to user
            assigned_issues = await self._get_assigned_issues(client, username, start_date, end_date)

            # Get issues reported by user
            reported_issues = await self._get_reported_issues(client, username, start_date, end_date)

            # Get issues where user has activity (comments, status changes, etc.)
            activity_issues = await self._get_user_activity_issues(client, username, start_date, end_date)

            # Combine and deduplicate
            all_issues_map = {}
            for issue in assigned_issues + reported_issues + activity_issues:
                issue_key = issue["key"]
                if issue_key not in all_issues_map:
                    all_issues_map[issue_key] = issue

            return {
                "username": username,
                "assigned_issues": assigned_issues,
                "reported_issues": reported_issues,
                "all_issues": list(all_issues_map.values()),
                "summary": {
                    "total_assigned": len(assigned_issues),
                    "total_reported": len(reported_issues),
                    "total_involved": len(all_issues_map)
                }
            }

    async def _get_assigned_issues(
        self,
        client: httpx.AsyncClient,
        username: str,
        start_date: date,
        end_date: date
    ) -> list[dict]:
        """Get issues assigned to user in the date range."""
        jql = f'assignee = "{username}" AND updated >= "{start_date}" AND updated <= "{end_date}"'

        if self.project_keys:
            project_filter = " OR ".join([f'project = "{key}"' for key in self.project_keys])
            jql = f"({project_filter}) AND {jql}"

        return await self._search_issues(client, jql)

    async def _get_reported_issues(
        self,
        client: httpx.AsyncClient,
        username: str,
        start_date: date,
        end_date: date
    ) -> list[dict]:
        """Get issues reported by user in the date range."""
        jql = f'reporter = "{username}" AND created >= "{start_date}" AND created <= "{end_date}"'

        if self.project_keys:
            project_filter = " OR ".join([f'project = "{key}"' for key in self.project_keys])
            jql = f"({project_filter}) AND {jql}"

        return await self._search_issues(client, jql)

    async def _get_user_activity_issues(
        self,
        client: httpx.AsyncClient,
        username: str,
        start_date: date,
        end_date: date
    ) -> list[dict]:
        """Get issues where user has recent activity (comments, etc.)."""
        # This is a broader search - issues where user is mentioned or has commented
        jql = f'updated >= "{start_date}" AND updated <= "{end_date}"'

        if self.project_keys:
            project_filter = " OR ".join([f'project = "{key}"' for key in self.project_keys])
            jql = f"({project_filter}) AND {jql}"

        issues = await self._search_issues(client, jql)

        # Filter to only issues where this user has activity
        filtered_issues = []
        for issue in issues:
            # Check if user is in assignee, reporter, or has comments
            if await self._user_has_activity(client, issue["key"], username):
                filtered_issues.append(issue)

        return filtered_issues

    async def _search_issues(self, client: httpx.AsyncClient, jql: str) -> list[dict]:
        """Search issues using JQL."""
        issues = []

        try:
            response = await client.post(
                f"{self.url}/rest/api/2/search",
                headers=self.headers,
                json={
                    "jql": jql,
                    "maxResults": 100,
                    "fields": ["summary", "status", "assignee", "reporter", "created", "updated", "priority", "issuetype"]
                }
            )
            response.raise_for_status()
            data = response.json()

            for issue in data.get("issues", []):
                fields = issue["fields"]
                issues.append({
                    "key": issue["key"],
                    "summary": fields["summary"],
                    "status": fields["status"]["name"],
                    "assignee": fields["assignee"]["displayName"] if fields.get("assignee") else None,
                    "reporter": fields["reporter"]["displayName"] if fields.get("reporter") else None,
                    "created": fields["created"],
                    "updated": fields["updated"],
                    "priority": fields["priority"]["name"] if fields.get("priority") else None,
                    "type": fields["issuetype"]["name"],
                    "url": f"{self.url}/browse/{issue['key']}"
                })
        except Exception as e:
            print(f"Error searching issues: {e}")

        return issues

    async def _user_has_activity(self, client: httpx.AsyncClient, issue_key: str, username: str) -> bool:
        """Check if user has activity on an issue."""
        try:
            # Get issue comments
            response = await client.get(
                f"{self.url}/rest/api/2/issue/{issue_key}/comment",
                headers=self.headers
            )
            response.raise_for_status()
            data = response.json()

            # Check if user has commented
            for comment in data.get("comments", []):
                author = comment.get("author", {})
                if author.get("emailAddress") == username or author.get("name") == username:
                    return True

        except Exception as e:
            print(f"Error checking user activity for {issue_key}: {e}")

        return False

    async def get_issue_details(self, issue_key: str) -> Optional[dict]:
        """
        Get detailed information about a specific issue.

        Args:
            issue_key: Issue key (e.g., PROJ-123)

        Returns:
            Issue details or None if not found
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.url}/rest/api/2/issue/{issue_key}",
                    headers=self.headers,
                    params={
                        "fields": "summary,description,status,assignee,reporter,created,updated,priority,issuetype,labels,comment"
                    }
                )
                response.raise_for_status()
                issue = response.json()
                fields = issue["fields"]

                # Get comments
                comments = []
                for comment in fields.get("comment", {}).get("comments", []):
                    comments.append({
                        "author": comment["author"]["displayName"],
                        "body": comment["body"],
                        "created": comment["created"]
                    })

                return {
                    "key": issue["key"],
                    "summary": fields["summary"],
                    "description": fields.get("description", ""),
                    "status": fields["status"]["name"],
                    "assignee": fields["assignee"]["displayName"] if fields.get("assignee") else None,
                    "reporter": fields["reporter"]["displayName"] if fields.get("reporter") else None,
                    "created": fields["created"],
                    "updated": fields["updated"],
                    "priority": fields["priority"]["name"] if fields.get("priority") else None,
                    "type": fields["issuetype"]["name"],
                    "labels": fields.get("labels", []),
                    "comments": comments,
                    "url": f"{self.url}/browse/{issue['key']}"
                }
            except Exception as e:
                print(f"Error getting issue details: {e}")
                return None