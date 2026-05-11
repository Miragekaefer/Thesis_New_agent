# tools.py
"""
Enterprise / Thesis-Level Jira Tool Layer
-----------------------------------------

Purpose:
- AI-facing business logic layer
- Input normalization
- Validation
- Multi-step orchestration
- Friendly outputs
- Safe write actions
- Reusable tool registry

This file should contain NO raw HTTP logic.
That belongs in jira_api.py
"""

from datetime import datetime, timedelta

from jira_api import (
    resolve_user,
    search_issues,
    create_issue,
    get_projects,
    get_issue,
    get_users,
    get_priorities,
    get_issue_types,
    get_fields,
    get_sprints,
)

from mysql_api import (
    execute_select_query,
    test_connection
)

# =========================================================
# GENERIC HELPERS
# =========================================================

def ok(data=None, message=None, **extra):
    payload = {"success": True}
    if data is not None:
        payload["data"] = data
    if message:
        payload["message"] = message
    payload.update(extra)
    return payload


def fail(message, **extra):
    payload = {"success": False, "error": message}
    payload.update(extra)
    return payload


def ask(question, missing_fields=None):
    payload = {
        "success": True,
        "ask_user": True,
        "question": question
    }
    if missing_fields:
        payload["missing_fields"] = missing_fields
    return payload


def pick(data, *keys, default=None):
    """
    Return first populated alias field.
    """
    if not isinstance(data, dict):
        return default

    for key in keys:
        if key in data and data[key] not in [None, "", []]:
            return data[key]

    return default


def lower_text(value):
    return str(value).strip().lower()

def clean_optional(value):
    if value in ["", None, [], {}]:
        return None
    return value


def normalize_project_key(project):
    if not project:
        return project
    return project.strip().upper().replace("-", "")


def resolve_assignee(value):
    """
    STRICT RULE:
    Returns ONLY a valid Jira accountId OR None.

    Accepts:
    - display name ("Daniel Käfer")
    - dict {"accountId": "..."}
    - accountId string

    Rejects everything else.
    """

    if not value:
        return None

    # Case 1: dict input
    if isinstance(value, dict):
        return value.get("accountId")

    # Case 2: already looks like accountId
    if isinstance(value, str):
        v = value.strip()

        # VALID accountId format check (important)
        if ":" in v and len(v) > 10:
            return v

        # Otherwise treat as name → resolve
        try:
            user = resolve_user(v)
            if user and "accountId" in user:
                return user["accountId"]
        except:
            return None

    return None



# =========================================================
# VALIDATION HELPERS
# =========================================================

def validate_project(project_key):
    try:
        projects = get_projects()

        for p in projects:
            if p.get("key", "").lower() == project_key.lower():
                return True

        return False

    except:
        return False


def validate_issue_type(project_key, issue_type):
    try:
        types = get_issue_types(project_key)

        for t in types:
            if t["name"].lower() == issue_type.lower():
                return True

        return False

    except:
        return False


def validate_priority(priority_name):
    try:
        values = get_priorities()

        for p in values:
            if p.get("name", "").lower() == priority_name.lower():
                return True

        return False

    except:
        return False


# =========================================================
# NORMALIZATION HELPERS
# =========================================================

def normalize_issue_type(raw):
    if not raw:
        return "Task"

    value = lower_text(raw)

    mapping = {
        "task": "Task",
        "story": "Story",
        "bug": "Bug",
        "epic": "Epic",
        "incident": "Incident",
        "service request": "Service Request",
    }

    return mapping.get(value, raw)


def infer_priority(text):
    """
    Basic heuristic priority detector.
    """
    if not text:
        return None

    t = lower_text(text)

    if any(x in t for x in ["critical", "urgent", "production down", "sev1"]):
        return "Highest"

    if any(x in t for x in ["high", "important", "asap"]):
        return "High"

    if any(x in t for x in ["low", "minor", "nice to have"]):
        return "Low"

    return "Medium"


# =========================================================
# READ TOOLS
# =========================================================

def get_projects_tool(input_data):
    try:
        data = get_projects()

        simplified = [
            {
                "key": x.get("key"),
                "name": x.get("name")
            }
            for x in data
        ]

        return ok(data=simplified)

    except Exception as e:
        return fail(str(e))


def get_issue_tool(input_data):
    issue_key = pick(
        input_data,
        "issue_key",
        "issueKey",
        "ticket",
        "key"
    )

    if not issue_key:
        return ask(
            "Which issue key should I retrieve?",
            ["issue_key"]
        )

    try:
        data = get_issue(issue_key)

        fields = data.get("fields", {})

        result = {
            "key": data.get("key"),
            "summary": fields.get("summary"),
            "status": fields.get("status", {}).get("name"),
            "priority": fields.get("priority", {}).get("name"),
            "assignee": (
                fields.get("assignee", {}) or {}
            ).get("displayName"),
            "created": fields.get("created")
        }

        return ok(data=result)

    except Exception as e:
        return fail(str(e))


def get_users_tool(input_data):
    query = pick(
        input_data,
        "name",
        "query",
        "user"
    )

    if not query:
        return ask(
            "Which user should I search for?",
            ["name"]
        )

    try:
        users = get_users(query)

        return ok(data=users)

    except Exception as e:
        return fail(str(e))


def get_priorities_tool(input_data):
    try:
        data = get_priorities()

        values = [
            x.get("name")
            for x in data
        ]

        return ok(data=values)

    except Exception as e:
        return fail(str(e))


def get_issue_types_tool(input_data):
    project = pick(input_data, "project")

    if not project:
        return ask(
            "For which project should I list issue types?",
            ["project"]
        )

    try:
        data = get_issue_types(project)
        return ok(data=data)

    except Exception as e:
        return fail(str(e))


def get_project_fields_tool(input_data):
    project = pick(input_data, "project")

    if not project:
        return ask(
            "For which project should I inspect fields?",
            ["project"]
        )

    try:
        data = get_fields(project)
        return ok(data=data)

    except Exception as e:
        return fail(str(e))


def get_sprints_tool(input_data):
    project = pick(input_data, "project")

    if not project:
        return ask(
            "For which project should I list sprints?",
            ["project"]
        )

    try:
        data = get_sprints(project)
        return ok(data=data)

    except Exception as e:
        return fail(str(e))


# =========================================================
# USER RESOLUTION TOOL
# =========================================================

def resolve_user_tool(input_data):
    name = pick(
        input_data,
        "name",
        "user",
        "assignee",
        "person"
    )

    if not name:
        return ask(
            "Which user should I resolve?",
            ["name"]
        )

    try:
        result = resolve_user(name)

        if not result:
            return fail("User not found")

        return ok(data=result)

    except Exception as e:
        return fail(str(e))


# =========================================================
# SEARCH TOOL
# =========================================================

def search_issues_tool(input_data):
    """
    Smart search:
    Accept direct JQL or structured filters.
    """

    jql = pick(input_data, "jql")

    if not jql:
        clauses = []

        project = pick(input_data, "project")
        assignee = pick(input_data, "assignee", "accountId")
        status = pick(input_data, "status")
        sprint = pick(input_data, "sprint")
        priority = pick(input_data, "priority")

        if project:
            clauses.append(f'project = "{project}"')

        if assignee:
            clauses.append(f'assignee = "{assignee}"')

        if status:
            clauses.append(f'status = "{status}"')

        if sprint:
            clauses.append(f'Sprint = "{sprint}"')

        if priority:
            clauses.append(f'priority = "{priority}"')

        if clauses:
            jql = " AND ".join(clauses)

    if not jql:
        return ask(
            "Please provide search criteria or JQL.",
            ["jql"]
        )

    try:
        result = search_issues(jql)

        issues = result.get("issues", [])

        simplified = []

        for x in issues:
            fields = x.get("fields", {})

            simplified.append({
                "key": x.get("key"),
                "summary": fields.get("summary"),
                "status": fields.get("status", {}).get("name"),
                "priority": fields.get("priority", {}).get("name"),
            })

        return ok(
            data=simplified,
            count=len(simplified),
            jql_used=jql
        )

    except Exception as e:
        return fail(str(e), jql_used=jql)


# =========================================================
# SAFE CREATE TOOL
# =========================================================

def plan_ticket_tool(input_data):
    """
    Step 1: Build a complete ticket plan.
    NO Jira writes allowed.
    """

    project = normalize_project_key(
        pick(input_data, "project", "projectKey")
    )

    summary = pick(input_data, "summary", "title")
    description = pick(input_data, "description", default="")

    issue_type = normalize_issue_type(
        pick(input_data, "issue_type", "type", default="Task")
    )

    assignee_raw = pick(input_data, "assignee", "owner")

    # Resolve user immediately (but still no execution)
    assignee_id = None
    assignee_display = None

    if assignee_raw:
        try:
            user = resolve_user(assignee_raw)
        except:
            user = None
        if user:
            assignee_id = user.get("accountId")
            assignee_display = user.get("displayName")

    # validations (no failure = planning stage)
    missing = []
    if not project:
        missing.append("project")
    if not summary:
        missing.append("summary")

    return ok(
        data={
            "project": project,
            "summary": summary,
            "description": description,
            "issue_type": issue_type,
            "assignee": {
                "raw": assignee_raw,
                "accountId": assignee_id,
                "displayName": assignee_display
            },
            "ready_to_execute": bool(project and summary and assignee_id),
            "missing_fields": [
                f for f in ["project", "summary", "assignee"]
                if not {
                    "project": project,
                    "summary": summary,
                    "assignee": assignee_id
                }[f]
            ]
        },
        message="Ticket plan created. Requires confirmation before execution."
    )

def execute_ticket_tool(input_data):
    """
    Step 2: Executes a previously planned ticket.
    HARD REQUIREMENT: must receive a full validated plan.
    """

    plan = pick(input_data, "plan")

    if not plan:
        return fail("Missing plan. You must call plan_ticket first.")

    project = normalize_project_key(plan.get("project"))
    summary = plan.get("summary")
    description = plan.get("description", "")
    issue_type = plan.get("issue_type", "Task")

    assignee = plan.get("assignee", {})
    assignee_id = assignee.get("accountId")

    # HARD SAFETY GATE
    if not project or not summary:
        return fail("Invalid plan: missing required fields")

    if not assignee_id:
        return fail("Invalid plan: unresolved assignee")

    # FINAL EXECUTION
    try:
        result = create_issue(
            project_key=project,
            summary=summary,
            description=description,
            issue_type=issue_type,
            assignee=assignee_id
        )

        return ok(
            data=result,
            message="Ticket created successfully from approved plan.",
            meta={
                "project": project,
                "issue_type": issue_type
            }
        )

    except Exception as e:
        return fail(str(e))



# =========================================================
# REPORTING TOOLS
# =========================================================

def sprint_closed_tickets_tool(input_data):
    sprint = pick(
        input_data,
        "sprint",
        "name"
    )

    if not sprint:
        return ask(
            "Which sprint should I analyze?",
            ["sprint"]
        )

    jql = f'Sprint = "{sprint}" AND statusCategory = Done'

    try:
        result = search_issues(jql)

        return ok(
            count=len(result.get("issues", [])),
            sprint=sprint,
            jql_used=jql
        )

    except Exception as e:
        return fail(str(e))


def workload_tool(input_data):
    """
    Open tickets for one assignee.
    """

    person = pick(
        input_data,
        "name",
        "assignee",
        "user"
    )

    if not person:
        return ask(
            "Whose workload should I inspect?",
            ["name"]
        )

    try:
        user = resolve_user(person)

        if not user:
            return fail("User not found")

        jql = (
            f'assignee = "{user["accountId"]}" '
            f'AND statusCategory != Done'
        )

        result = search_issues(jql)

        return ok(
            user=user["displayName"],
            count=len(result.get("issues", [])),
            jql_used=jql
        )

    except Exception as e:
        return fail(str(e))


# =========================================================
# INTELLIGENCE TOOLS
# =========================================================

def route_department_tool(input_data):
    text = pick(
        input_data,
        "description",
        "summary",
        "text",
        default=""
    ).lower()

    if "printer" in text:
        project = "PRINT"

    elif "website" in text:
        project = "WEB"

    elif "analytics" in text:
        project = "PA"

    elif "login" in text or "access" in text:
        project = "IT"

    else:
        project = "SUPPORT"

    return ok(
        project=project,
        message=f"Recommended project: {project}"
    )


def db_lookup_tool(input_data):
    production_id = pick(
        input_data,
        "production_id",
        "id"
    )

    if not production_id:
        return ask(
            "Which production ID should I search?",
            ["production_id"]
        )

    return fail(
        f"Database integration not implemented for {production_id}",
        future_tool=True
    )


def ask_user_tool(input_data):
    question = pick(
        input_data,
        "question",
        default="Please provide more details."
    )

    return ask(question)


# =========================================================
# MYSQL DATABASE TOOLS
# =========================================================

ALLOWED_TABLES = [
    "customers",
    "orders",
    "incidents",
    "production",
]


def validate_sql_query(query):
    """
    VERY IMPORTANT SECURITY LAYER

    Only allow:
    - SELECT
    - SHOW
    - DESCRIBE

    Block:
    - DELETE
    - DROP
    - UPDATE
    - INSERT
    """

    if not query:
        return False

    q = query.strip().lower()

    blocked = [
        "delete",
        "drop",
        "truncate",
        "update",
        "insert",
        "alter",
        "grant",
        "revoke",
    ]

    if any(word in q for word in blocked):
        return False

    allowed = (
        q.startswith("select")
        or q.startswith("show")
        or q.startswith("describe")
    )

    return allowed


def database_query_tool(input_data):
    """
    Generic READ-ONLY database tool.
    """

    query = pick(input_data, "query", "sql")

    if not query:
        return ask(
            "Which SQL query should I execute?",
            ["query"]
        )

    # SECURITY VALIDATION
    if not validate_sql_query(query):
        return fail(
            "Unsafe SQL query rejected."
        )

    try:
        result = execute_select_query(query)

        return ok(
            data=result.get("rows", []),
            count=result.get("count", 0),
            query=query
        )

    except Exception as e:
        return fail(str(e))


def database_health_tool(input_data):
    """
    MySQL connection health check.
    """

    try:
        result = test_connection()

        return result

    except Exception as e:
        return fail(str(e))

# =========================================================
# REGISTRY (UPDATED FOR PLAN → EXECUTE)
# =========================================================

TOOLS = {
    # Planning layer
    "plan_ticket_creation": {
        "handler": plan_ticket_tool,
        "type": "plan"
    },
    "execute_ticket_creation": {
        "handler": execute_ticket_tool,
        "type": "execute"
    },

    # Read
    "get_projects": {
        "handler": get_projects_tool,
        "type": "read"
    },
    "get_issue": {
        "handler": get_issue_tool,
        "type": "read"
    },
    "get_users": {
        "handler": get_users_tool,
        "type": "read"
    },
    "get_priorities": {
        "handler": get_priorities_tool,
        "type": "read"
    },
    "get_issue_types": {
        "handler": get_issue_types_tool,
        "type": "read"
    },
    "get_project_fields": {
        "handler": get_project_fields_tool,
        "type": "read"
    },
    "get_sprints": {
        "handler": get_sprints_tool,
        "type": "read"
    },

    # Identity
    "resolve_user": {
        "handler": resolve_user_tool,
        "type": "read"
    },

    # Search / Reports
    "search_issues": {
        "handler": search_issues_tool,
        "type": "read"
    },
    "sprint_closed_tickets": {
        "handler": sprint_closed_tickets_tool,
        "type": "read"
    },
    "workload": {
        "handler": workload_tool,
        "type": "read"
    },

    # Intelligence
    "route_department": {
        "handler": route_department_tool,
        "type": "read"
    },
    "db_lookup": {
        "handler": db_lookup_tool,
        "type": "read"
    },
    "ask_user": {
        "handler": ask_user_tool,
        "type": "read"
    },

    # MySQL
    "database_query": {
        "handler": database_query_tool,
        "type": "read"
    },
    "database_health": {
        "handler": database_health_tool,
        "type": "read"
    },
}