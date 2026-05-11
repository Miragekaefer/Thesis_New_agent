import time
import requests
from requests.auth import HTTPBasicAuth
from config import (
    JIRA_URL,
    JIRA_EMAIL,
    JIRA_TOKEN,
    REQUEST_TIMEOUT,
    JIRA_MAX_RESULTS
)

# =====================================================
# AUTH / HEADERS
# =====================================================

auth = HTTPBasicAuth(JIRA_EMAIL, JIRA_TOKEN)

headers = {
    "Accept": "application/json",
    "Content-Type": "application/json"
}


# =====================================================
# CUSTOM EXCEPTION
# =====================================================

class JiraAPIError(Exception):
    pass


# =====================================================
# CORE REQUEST ENGINE
# =====================================================

def request(method, endpoint, params=None, payload=None, retries=2):
    url = f"{JIRA_URL}{endpoint}"

    for attempt in range(retries + 1):
        try:
            r = requests.request(
                method=method,
                url=url,
                headers=headers,
                auth=auth,
                params=params,
                json=payload,
                timeout=REQUEST_TIMEOUT
            )

            if r.ok:
                if r.text.strip():
                    return r.json()
                return {}

            detail = r.text
            try:
                detail = r.json()
            except:
                pass

            # Retry transient errors
            if r.status_code in [429, 500, 502, 503]:
                if attempt < retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue

            raise JiraAPIError(
                f"{method} {endpoint} failed "
                f"HTTP {r.status_code}: {detail}"
            )

        except requests.Timeout:
            if attempt < retries:
                time.sleep(1)
                continue
            raise JiraAPIError("Request timeout")

        except requests.RequestException as e:
            raise JiraAPIError(str(e))


# =====================================================
# WRAPPERS
# =====================================================

def jira_get(endpoint, params=None):
    return request("GET", endpoint, params=params)


def jira_post(endpoint, payload=None):
    return request("POST", endpoint, payload=payload)


def jira_put(endpoint, payload=None):
    return request("PUT", endpoint, payload=payload)


# =====================================================
# SEARCH
# =====================================================

def search_issues(jql, max_results=JIRA_MAX_RESULTS):
    return jira_post(
        "/search/jql",
        {
            "jql": jql,
            "maxResults": max_results,
            "fields": [
                "summary",
                "status",
                "assignee",
                "priority",
                "created"
            ]
        }
    )


# =====================================================
# USERS
# =====================================================

def resolve_user(query):
    users = jira_get(
        "/user/search",
        params={"query": query}
    )

    if not users:
        return None

    best = users[0]

    return {
        "accountId": best.get("accountId"),
        "displayName": best.get("displayName")
    }


def get_users(query):
    users = jira_get(
        "/user/search",
        params={"query": query}
    )

    return [
        {
            "accountId": u.get("accountId"),
            "displayName": u.get("displayName"),
            "emailAddress": u.get("emailAddress", "")
        }
        for u in users
    ]


# =====================================================
# ISSUES
# =====================================================

def create_issue(
    project_key,
    summary,
    description="",
    issue_type="Task",
    assignee=None,
    priority=None,
    labels=None
):
    fields = {
        "project": {"key": project_key},
        "summary": summary,
        "issuetype": {"name": issue_type},
        "description": {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": description
                        }
                    ]
                }
            ]
        }
    }

    if assignee:
        fields["assignee"] = {"id": assignee}

    if priority:
        fields["priority"] = {"name": priority}

    if labels:
        fields["labels"] = labels

    return jira_post(
        "/issue",
        {"fields": fields}
    )


def get_issue(issue_key):
    return jira_get(f"/issue/{issue_key}")


def assign_issue(issue_key, account_id):
    return jira_put(
        f"/issue/{issue_key}/assignee",
        {"accountId": account_id}
    )


def add_comment(issue_key, text):
    payload = {
        "body": {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": text
                        }
                    ]
                }
            ]
        }
    }

    return jira_post(
        f"/issue/{issue_key}/comment",
        payload
    )


# =====================================================
# METADATA
# =====================================================

def get_projects():
    return jira_get("/project")


def get_priorities():
    return jira_get("/priority")


def get_issue_types(project):
    data = jira_get(f"/project/{project}")

    return [
        {
            "id": x.get("id"),
            "name": x.get("name"),
            "description": x.get("description", "")
        }
        for x in data.get("issueTypes", [])
    ]


def get_fields(project):
    data = jira_get(
        "/issue/createmeta",
        params={
            "projectKeys": project,
            "expand": "projects.issuetypes.fields"
        }
    )

    projects = data.get("projects", [])
    if not projects:
        return []

    result = []

    for issue_type in projects[0].get("issuetypes", []):
        for field_id, meta in issue_type.get("fields", {}).items():
            result.append({
                "issue_type": issue_type["name"],
                "field_id": field_id,
                "name": meta.get("name"),
                "required": meta.get("required", False)
            })

    return result


# =====================================================
# SPRINTS
# =====================================================

def get_sprints(project):
    boards = jira_get(
        "/board",
        params={"projectKeyOrId": project}
    )

    values = boards.get("values", [])
    if not values:
        return []

    board_id = values[0]["id"]

    sprints = jira_get(
        f"/board/{board_id}/sprint"
    )

    return [
        {
            "id": s.get("id"),
            "name": s.get("name"),
            "state": s.get("state")
        }
        for s in sprints.get("values", [])
    ]