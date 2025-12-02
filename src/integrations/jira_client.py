"""Jira API client for fetching team activity (DC version)."""

import httpx
import base64
from datetime import date
from typing import Optional


class JiraClient:
    """Client for interacting with Jira Data Center API (REST API v2)."""

    def __init__(self, url: str, username: str, api_token: str, project_keys: Optional[list[str]] = None):
        """
        Initialize Jira client.

        Args:
            url: Jira instance URL (e.g., https://jira.example.com)
            username: Jira username
            api_token: API token or password
            project_keys: Specific project keys to track, None = all accessible
        """
        self.url = url.rstrip("/")
        self.username = username
        self.api_token = api_token
        self.project_keys = project_keys

        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }

    async def get_user_activity(
        self,
        username: str,
        start_date: date,
        end_date: date
    ) -> dict:
        """
        Get user's activity for a specific date range, including worklogs.

        Args:
            username: Jira username
            start_date: Start date
            end_date: End date

        Returns:
            Dictionary with activity summary including worklogs
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Get issues assigned to user
            assigned_issues = await self._get_assigned_issues(client, username, start_date, end_date)

            # Get issues reported by user
            reported_issues = await self._get_reported_issues(client, username, start_date, end_date)

            # Get worklogs - this is the key addition
            worklogs = await self._get_user_worklogs(client, username, start_date, end_date)

            # Combine all involved issues
            all_issues_map = {}
            for issue in assigned_issues + reported_issues:
                if issue["key"] not in all_issues_map:
                    all_issues_map[issue["key"]] = issue

            # Add issues from worklogs that aren't already tracked
            for worklog in worklogs:
                if worklog["issue_key"] not in all_issues_map:
                    all_issues_map[worklog["issue_key"]] = {
                        "key": worklog["issue_key"],
                        "summary": worklog["issue_summary"],
                        "status": None,
                        "type": None,
                        "url": f"{self.url}/browse/{worklog['issue_key']}"
                    }

            # Calculate total time spent
            total_seconds = sum(w["time_spent_seconds"] for w in worklogs)

            return {
                "username": username,
                "assigned_issues": assigned_issues,
                "reported_issues": reported_issues,
                "worklogs": worklogs,
                "all_issues": list(all_issues_map.values()),
                "summary": {
                    "total_assigned": len(assigned_issues),
                    "total_reported": len(reported_issues),
                    "total_involved": len(all_issues_map),
                    "total_worklog_entries": len(worklogs),
                    "total_time_spent_seconds": total_seconds,
                    "total_time_spent_formatted": self._format_seconds(total_seconds)
                }
            }

    async def _get_user_worklogs(
        self,
        client: httpx.AsyncClient,
        username: str,
        start_date: date,
        end_date: date
    ) -> list[dict]:
        """
        Get user's worklogs in the date range.

        Uses JQL with worklogAuthor and worklogDate to find issues,
        then fetches worklogs for each issue.
        """
        # Step 1: Find issues with worklogs by this user in the date range
        jql = f'worklogAuthor = "{username}" AND worklogDate >= "{start_date}" AND worklogDate <= "{end_date}"'

        if self.project_keys:
            project_filter = " OR ".join([f'project = "{key}"' for key in self.project_keys])
            jql = f"({project_filter}) AND {jql}"

        issue_keys = await self._search_issue_keys(client, jql)

        # Step 2: For each issue, get worklogs and filter by user and date
        all_worklogs = []
        for issue_key in issue_keys:
            issue_worklogs = await self._get_issue_worklogs(
                client, issue_key, username, start_date, end_date
            )
            all_worklogs.extend(issue_worklogs)

        # Sort by started time (most recent first)
        all_worklogs.sort(key=lambda x: x["started"], reverse=True)

        return all_worklogs

    async def _search_issue_keys(self, client: httpx.AsyncClient, jql: str) -> list[str]:
        """Search for issue keys using JQL with pagination."""
        all_keys = []
        start_at = 0
        max_results = 100

        while True:
            try:
                response = await client.post(
                    f"{self.url}/rest/api/2/search",
                    headers=self.headers,
                    json={
                        "jql": jql,
                        "startAt": start_at,
                        "maxResults": max_results,
                        "fields": ["key"]  # Only need key for this query
                    }
                )
                response.raise_for_status()
                data = response.json()

                issues = data.get("issues", [])
                all_keys.extend([issue["key"] for issue in issues])

                total = data.get("total", 0)
                if start_at + max_results >= total:
                    break
                start_at += max_results

            except Exception as e:
                print(f"Error searching issue keys: {e}")
                break

        return all_keys

    async def _get_issue_worklogs(
        self,
        client: httpx.AsyncClient,
        issue_key: str,
        username: str,
        start_date: date,
        end_date: date
    ) -> list[dict]:
        """
        Get worklogs for a specific issue, filtered by user and date range.

        Uses /rest/api/2/issue/{key}/worklog endpoint.
        """
        worklogs = []
        start_at = 0
        max_results = 100

        # Get issue summary first
        issue_summary = await self._get_issue_summary(client, issue_key)

        while True:
            try:
                response = await client.get(
                    f"{self.url}/rest/api/2/issue/{issue_key}/worklog",
                    headers=self.headers,
                    params={
                        "startAt": start_at,
                        "maxResults": max_results
                    }
                )
                response.raise_for_status()
                data = response.json()

                for log in data.get("worklogs", []):
                    # Get author info - DC uses 'name' or 'key', not 'accountId'
                    author = log.get("author", {})
                    author_name = author.get("name") or author.get("key") or author.get("displayName", "")

                    # Check if this worklog is by the target user
                    if author_name.lower() != username.lower():
                        # Also check displayName as fallback
                        if author.get("displayName", "").lower() != username.lower():
                            continue

                    # Parse and check date
                    started_str = log.get("started", "")
                    if started_str:
                        # Parse ISO date (e.g., "2025-01-15T10:00:00.000+0800")
                        started_date = self._parse_jira_date(started_str)
                        if started_date and start_date <= started_date <= end_date:
                            worklogs.append({
                                "issue_key": issue_key,
                                "issue_summary": issue_summary,
                                "project_key": issue_key.split("-")[0] if "-" in issue_key else "",
                                "author": author.get("displayName", author_name),
                                "time_spent": log.get("timeSpent", ""),
                                "time_spent_seconds": log.get("timeSpentSeconds", 0),
                                "started": started_str,
                                "started_date": started_date.isoformat(),
                                "comment": log.get("comment", ""),
                                "worklog_id": log.get("id")
                            })

                total = data.get("total", 0)
                if start_at + max_results >= total:
                    break
                start_at += max_results

            except Exception as e:
                print(f"Error getting worklogs for {issue_key}: {e}")
                break

        return worklogs

    async def _get_issue_summary(self, client: httpx.AsyncClient, issue_key: str) -> str:
        """Get issue summary."""
        try:
            response = await client.get(
                f"{self.url}/rest/api/2/issue/{issue_key}",
                headers=self.headers,
                params={"fields": "summary"}
            )
            response.raise_for_status()
            return response.json().get("fields", {}).get("summary", "")
        except Exception:
            return ""

    def _parse_jira_date(self, date_str: str) -> Optional[date]:
        """Parse Jira date string to date object."""
        if not date_str:
            return None
        try:
            # Handle format like "2025-01-15T10:00:00.000+0800"
            return date.fromisoformat(date_str[:10])
        except ValueError:
            return None

    def _format_seconds(self, seconds: int) -> str:
        """Format seconds to human readable string like '2h 30m'."""
        if seconds <= 0:
            return "0m"
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if hours > 0 and minutes > 0:
            return f"{hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h"
        else:
            return f"{minutes}m"

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

    async def _search_issues(self, client: httpx.AsyncClient, jql: str) -> list[dict]:
        """Search issues using JQL with full details."""
        issues = []
        start_at = 0
        max_results = 100

        while True:
            try:
                response = await client.post(
                    f"{self.url}/rest/api/2/search",
                    headers=self.headers,
                    json={
                        "jql": jql,
                        "startAt": start_at,
                        "maxResults": max_results,
                        "fields": ["summary", "status", "assignee", "reporter", "created", "updated", "priority", "issuetype", "parent"]
                    }
                )
                response.raise_for_status()
                data = response.json()

                for issue in data.get("issues", []):
                    fields = issue["fields"]
                    issues.append({
                        "key": issue["key"],
                        "summary": fields.get("summary", ""),
                        "status": fields["status"]["name"] if fields.get("status") else None,
                        "assignee": fields["assignee"]["displayName"] if fields.get("assignee") else None,
                        "reporter": fields["reporter"]["displayName"] if fields.get("reporter") else None,
                        "created": fields.get("created"),
                        "updated": fields.get("updated"),
                        "priority": fields["priority"]["name"] if fields.get("priority") else None,
                        "type": fields["issuetype"]["name"] if fields.get("issuetype") else None,
                        "parent_key": fields.get("parent", {}).get("key"),
                        "url": f"{self.url}/browse/{issue['key']}"
                    })

                total = data.get("total", 0)
                if start_at + max_results >= total:
                    break
                start_at += max_results

            except Exception as e:
                print(f"Error searching issues: {e}")
                break

        return issues

    async def get_issue_details(self, issue_key: str) -> Optional[dict]:
        """Get detailed information about a specific issue."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.url}/rest/api/2/issue/{issue_key}",
                    headers=self.headers,
                    params={
                        "fields": "summary,description,status,assignee,reporter,created,updated,priority,issuetype,labels,comment,parent,timetracking"
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

                # Get time tracking info
                time_tracking = fields.get("timetracking", {})

                return {
                    "key": issue["key"],
                    "summary": fields.get("summary", ""),
                    "description": fields.get("description", ""),
                    "status": fields["status"]["name"] if fields.get("status") else None,
                    "assignee": fields["assignee"]["displayName"] if fields.get("assignee") else None,
                    "reporter": fields["reporter"]["displayName"] if fields.get("reporter") else None,
                    "created": fields.get("created"),
                    "updated": fields.get("updated"),
                    "priority": fields["priority"]["name"] if fields.get("priority") else None,
                    "type": fields["issuetype"]["name"] if fields.get("issuetype") else None,
                    "labels": fields.get("labels", []),
                    "parent_key": fields.get("parent", {}).get("key"),
                    "time_estimate": time_tracking.get("originalEstimate"),
                    "time_spent": time_tracking.get("timeSpent"),
                    "time_remaining": time_tracking.get("remainingEstimate"),
                    "comments": comments,
                    "url": f"{self.url}/browse/{issue['key']}"
                }
            except Exception as e:
                print(f"Error getting issue details: {e}")
                return None

    async def get_worklog_summary_by_project(
        self,
        username: str,
        start_date: date,
        end_date: date
    ) -> dict:
        """
        Get worklog summary grouped by project.

        Returns time spent per project for the user.
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            worklogs = await self._get_user_worklogs(client, username, start_date, end_date)

            # Group by project
            project_totals = {}
            for log in worklogs:
                project_key = log["project_key"]
                if project_key not in project_totals:
                    project_totals[project_key] = {
                        "project_key": project_key,
                        "total_seconds": 0,
                        "worklog_count": 0,
                        "issues": set()
                    }
                project_totals[project_key]["total_seconds"] += log["time_spent_seconds"]
                project_totals[project_key]["worklog_count"] += 1
                project_totals[project_key]["issues"].add(log["issue_key"])

            # Format results
            results = []
            for project_key, data in project_totals.items():
                results.append({
                    "project_key": project_key,
                    "total_time_formatted": self._format_seconds(data["total_seconds"]),
                    "total_seconds": data["total_seconds"],
                    "worklog_count": data["worklog_count"],
                    "issue_count": len(data["issues"])
                })

            # Sort by time spent (descending)
            results.sort(key=lambda x: x["total_seconds"], reverse=True)

            return {
                "username": username,
                "period": f"{start_date} to {end_date}",
                "projects": results,
                "total_time_formatted": self._format_seconds(sum(p["total_seconds"] for p in results))
            }