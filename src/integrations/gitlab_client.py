"""GitLab API client for fetching team activity."""

import httpx
from datetime import date
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class GitLabEvent:
    """Represents a GitLab contribution event."""
    id: int
    action_name: str
    target_type: Optional[str]
    target_id: Optional[int]
    target_iid: Optional[int]
    target_title: Optional[str]
    project_id: Optional[int]
    created_at: str
    push_data: Optional[dict] = None
    note: Optional[dict] = None


@dataclass
class UserActivity:
    """User activity summary."""
    username: str
    events: list[GitLabEvent] = field(default_factory=list)

    # Categorized events
    push_events: list[dict] = field(default_factory=list)
    merge_request_events: list[dict] = field(default_factory=list)
    issue_events: list[dict] = field(default_factory=list)
    comment_events: list[dict] = field(default_factory=list)
    other_events: list[dict] = field(default_factory=list)

    @property
    def summary(self) -> dict:
        return {
            "total_events": len(self.events),
            "total_pushes": len(self.push_events),
            "total_commits": sum(e.get("commit_count", 0) for e in self.push_events),
            "total_merge_requests": len(self.merge_request_events),
            "total_issues": len(self.issue_events),
            "total_comments": len(self.comment_events)
        }


class GitLabClient:
    """Client for interacting with GitLab API."""

    def __init__(self, url: str, token: str, project_ids: Optional[list[int]] = None):
        """
        Initialize GitLab client.

        Args:
            url: GitLab instance URL (e.g., https://gitlab.example.com)
            token: Personal access token (needs read_user or api scope)
            project_ids: Specific project IDs to track, None = all
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
        end_date: date,
        target_type: Optional[str] = None,
        action: Optional[str] = None
    ) -> dict:
        """
        Get user's contribution events for a specific date range.

        Uses the /users/:id/events API endpoint.

        Args:
            username: GitLab username or user ID
            start_date: Start date (after)
            end_date: End date (before)
            target_type: Filter by target type (issue, merge_request, etc.)
            action: Filter by action type

        Returns:
            Dictionary with categorized activity
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Get user ID if username is provided
            user_id = await self._get_user_id(client, username)
            if not user_id:
                return {
                    "error": f"User {username} not found",
                    "username": username,
                    "events": [],
                    "push_events": [],
                    "merge_request_events": [],
                    "issue_events": [],
                    "comment_events": [],
                    "summary": {
                        "total_events": 0,
                        "total_pushes": 0,
                        "total_commits": 0,
                        "total_merge_requests": 0,
                        "total_issues": 0,
                        "total_comments": 0
                    }
                }

            # Fetch all events using pagination
            all_events = await self._fetch_user_events(
                client, user_id, start_date, end_date, target_type, action
            )

            # Filter by project IDs if specified
            if self.project_ids:
                all_events = [e for e in all_events if e.get("project_id") in self.project_ids]

            # Categorize events
            activity = self._categorize_events(username, all_events)

            return {
                "username": username,
                "user_id": user_id,
                "events": all_events,
                "push_events": activity.push_events,
                "merge_request_events": activity.merge_request_events,
                "issue_events": activity.issue_events,
                "comment_events": activity.comment_events,
                "other_events": activity.other_events,
                "summary": activity.summary
            }

    async def _get_user_id(self, client: httpx.AsyncClient, username: str) -> Optional[int]:
        """Get user ID from username."""
        # If username is already an ID, return it
        if isinstance(username, int) or username.isdigit():
            return int(username)

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
            print(f"Error getting user ID for {username}: {e}")
        return None

    async def _fetch_user_events(
        self,
        client: httpx.AsyncClient,
        user_id: int,
        start_date: date,
        end_date: date,
        target_type: Optional[str] = None,
        action: Optional[str] = None
    ) -> list[dict]:
        """
        Fetch user events with pagination.

        Uses GET /users/:id/events endpoint.
        """
        all_events = []
        page = 1
        per_page = 100

        while True:
            params = {
                "after": start_date.isoformat(),
                "before": end_date.isoformat(),
                "sort": "desc",
                "page": page,
                "per_page": per_page
            }

            if target_type:
                params["target_type"] = target_type
            if action:
                params["action"] = action

            try:
                response = await client.get(
                    f"{self.url}/api/v4/users/{user_id}/events",
                    headers=self.headers,
                    params=params
                )
                response.raise_for_status()
                events = response.json()

                if not events:
                    break

                all_events.extend(events)

                # Check if we've reached the last page
                if len(events) < per_page:
                    break

                page += 1

                # Safety limit to avoid infinite loops
                if page > 50:
                    break

            except Exception as e:
                print(f"Error fetching events for user {user_id}, page {page}: {e}")
                break

        return all_events

    def _categorize_events(self, username: str, events: list[dict]) -> UserActivity:
        """Categorize events by type."""
        activity = UserActivity(username=username)

        for event in events:
            action_name = event.get("action_name", "")
            target_type = event.get("target_type")

            event_info = {
                "id": event.get("id"),
                "action_name": action_name,
                "project_id": event.get("project_id"),
                "created_at": event.get("created_at"),
                "target_id": event.get("target_id"),
                "target_iid": event.get("target_iid"),
                "target_title": event.get("target_title"),
            }

            # Push events (code commits)
            if action_name == "pushed":
                push_data = event.get("push_data", {})
                event_info.update({
                    "commit_count": push_data.get("commit_count", 0),
                    "ref": push_data.get("ref"),
                    "ref_type": push_data.get("ref_type"),
                    "commit_from": push_data.get("commit_from"),
                    "commit_to": push_data.get("commit_to"),
                    "commit_title": push_data.get("commit_title"),
                    "action": push_data.get("action")
                })
                activity.push_events.append(event_info)

            # Merge request events
            elif target_type == "MergeRequest":
                activity.merge_request_events.append(event_info)

            # Issue events
            elif target_type == "Issue":
                activity.issue_events.append(event_info)

            # Comment/Note events
            elif target_type == "Note" or action_name == "commented on":
                note_data = event.get("note", {})
                event_info.update({
                    "note_body": note_data.get("body", "")[:200],  # Truncate long notes
                    "noteable_type": note_data.get("noteable_type"),
                    "noteable_id": note_data.get("noteable_id")
                })
                activity.comment_events.append(event_info)

            # Other events (milestone, wiki, etc.)
            else:
                activity.other_events.append(event_info)

            activity.events.append(event)

        return activity

    async def get_user_events_by_type(
        self,
        username: str,
        start_date: date,
        end_date: date,
        target_type: str
    ) -> list[dict]:
        """
        Get user events filtered by target type.

        Args:
            username: GitLab username
            start_date: Start date
            end_date: End date
            target_type: One of: issue, merge_request, milestone, note, project, snippet, user

        Returns:
            List of events
        """
        result = await self.get_user_activity(
            username, start_date, end_date, target_type=target_type
        )
        return result.get("events", [])

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
                    "iid": issue["iid"],
                    "title": issue["title"],
                    "description": issue.get("description"),
                    "state": issue["state"],
                    "created_at": issue["created_at"],
                    "updated_at": issue["updated_at"],
                    "closed_at": issue.get("closed_at"),
                    "labels": issue.get("labels", []),
                    "assignees": [a["name"] for a in issue.get("assignees", [])],
                    "author": issue.get("author", {}).get("name"),
                    "web_url": issue["web_url"]
                }
            except Exception as e:
                print(f"Error getting issue details: {e}")
                return None

    async def get_merge_request_details(self, project_id: int, mr_iid: int) -> Optional[dict]:
        """
        Get detailed information about a specific merge request.

        Args:
            project_id: Project ID
            mr_iid: MR IID (internal ID)

        Returns:
            MR details or None if not found
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.url}/api/v4/projects/{project_id}/merge_requests/{mr_iid}",
                    headers=self.headers
                )
                response.raise_for_status()
                mr = response.json()

                return {
                    "iid": mr["iid"],
                    "title": mr["title"],
                    "description": mr.get("description"),
                    "state": mr["state"],
                    "created_at": mr["created_at"],
                    "updated_at": mr["updated_at"],
                    "merged_at": mr.get("merged_at"),
                    "source_branch": mr["source_branch"],
                    "target_branch": mr["target_branch"],
                    "labels": mr.get("labels", []),
                    "assignees": [a["name"] for a in mr.get("assignees", [])],
                    "author": mr.get("author", {}).get("name"),
                    "web_url": mr["web_url"]
                }
            except Exception as e:
                print(f"Error getting MR details: {e}")
                return None

    async def get_project_info(self, project_id: int) -> Optional[dict]:
        """Get project information."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.url}/api/v4/projects/{project_id}",
                    headers=self.headers
                )
                response.raise_for_status()
                project = response.json()

                return {
                    "id": project["id"],
                    "name": project["name"],
                    "path": project["path"],
                    "path_with_namespace": project["path_with_namespace"],
                    "web_url": project["web_url"]
                }
            except Exception as e:
                print(f"Error getting project info: {e}")
                return None
