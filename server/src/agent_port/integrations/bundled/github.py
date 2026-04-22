from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    RemoteMcpIntegration,
    TokenAuth,
)

_TOOL_CATEGORIES: dict[str, str] = {
    # Actions
    "actions_get": "Actions",
    "actions_list": "Actions",
    "actions_run_trigger": "Actions",
    "get_job_logs": "Actions",
    # Code security
    "get_code_scanning_alert": "Code security",
    "list_code_scanning_alerts": "Code security",
    # Context
    "get_me": "Context",
    "get_team_members": "Context",
    "get_teams": "Context",
    # Copilot
    "assign_copilot_to_issue": "Copilot",
    "request_copilot_review": "Copilot",
    # Dependabot
    "get_dependabot_alert": "Dependabot",
    "list_dependabot_alerts": "Dependabot",
    # Discussions
    "get_discussion": "Discussions",
    "get_discussion_comments": "Discussions",
    "list_discussion_categories": "Discussions",
    "list_discussions": "Discussions",
    # Gists
    "create_gist": "Gists",
    "get_gist": "Gists",
    "list_gists": "Gists",
    "update_gist": "Gists",
    # Git
    "get_repository_tree": "Git",
    # Issues
    "add_issue_comment": "Issues",
    "issue_read": "Issues",
    "issue_write": "Issues",
    "list_issue_types": "Issues",
    "list_issues": "Issues",
    "search_issues": "Issues",
    "sub_issue_write": "Issues",
    # Labels
    "get_label": "Labels",
    "label_write": "Labels",
    "list_label": "Labels",
    # Notifications
    "dismiss_notification": "Notifications",
    "get_notification_details": "Notifications",
    "list_notifications": "Notifications",
    "manage_notification_subscription": "Notifications",
    "manage_repository_notification_subscription": "Notifications",
    "mark_all_notifications_read": "Notifications",
    # Organizations
    "search_orgs": "Organizations",
    # Projects
    "projects_get": "Projects",
    "projects_list": "Projects",
    "projects_write": "Projects",
    # Pull requests
    "add_comment_to_pending_review": "Pull requests",
    "add_reply_to_pull_request_comment": "Pull requests",
    "create_pull_request": "Pull requests",
    "list_pull_requests": "Pull requests",
    "merge_pull_request": "Pull requests",
    "pull_request_read": "Pull requests",
    "pull_request_review_write": "Pull requests",
    "search_pull_requests": "Pull requests",
    "update_pull_request": "Pull requests",
    "update_pull_request_branch": "Pull requests",
    # Repositories
    "create_branch": "Repositories",
    "create_or_update_file": "Repositories",
    "create_repository": "Repositories",
    "delete_file": "Repositories",
    "fork_repository": "Repositories",
    "get_commit": "Repositories",
    "get_file_contents": "Repositories",
    "get_latest_release": "Repositories",
    "get_release_by_tag": "Repositories",
    "get_tag": "Repositories",
    "list_branches": "Repositories",
    "list_commits": "Repositories",
    "list_releases": "Repositories",
    "list_tags": "Repositories",
    "push_files": "Repositories",
    "search_code": "Repositories",
    "search_repositories": "Repositories",
    # Secret protection
    "get_secret_scanning_alert": "Secret protection",
    "list_secret_scanning_alerts": "Secret protection",
    # Security advisories
    "get_global_security_advisory": "Security advisories",
    "list_global_security_advisories": "Security advisories",
    "list_org_repository_security_advisories": "Security advisories",
    "list_repository_security_advisories": "Security advisories",
    # Stargazers
    "list_starred_repositories": "Stargazers",
    "star_repository": "Stargazers",
    "unstar_repository": "Stargazers",
    # Users
    "search_users": "Users",
}


class GitHubIntegration(RemoteMcpIntegration):
    id: str = "github"
    name: str = "GitHub"
    description: str = "Repos, issues, PRs, Actions, and more"
    docs_url: str = "https://github.com/github/github-mcp-server"
    url: str = "https://api.githubcopilot.com/mcp/"
    auth: list[AuthMethod] = Field(
        default=[
            TokenAuth(
                method="token",
                label="GitHub Personal Access Token",
                header="Authorization",
                format="Bearer {token}",
            ),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
