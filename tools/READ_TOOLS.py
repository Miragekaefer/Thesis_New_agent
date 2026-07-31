# tools/READ_TOOLS.py

from jira_api import (
    resolve_user,
    search_issues,
    get_projects,
    get_issue,
    get_users,
    get_priorities,
    get_issue_types,
    get_fields,
    get_sprints,
)
from mysql_api import (execute_select_query,test_connection)
from tools.HELPERS import (ok,fail,ask,pick,)

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
    """
    Look up production information by ID and return
    relevant details for ticket creation.
    """
    production_id = pick(
        input_data,
        "production_id",
        "id",
        "productionId"
    )

    if not production_id:
        return ask(
            "Which production ID should I search?",
            ["production_id"]
        )

    try:
        # Query production data
        query = f"""
            SELECT *
            FROM production
            WHERE id = '{production_id}'
            LIMIT 1
        """

        if not validate_sql_query(query):
            return fail("Invalid production ID format")

        result = execute_select_query(query)
        rows = result.get("rows", [])

        if not rows:
            return fail(
                f"No production record found for ID: {production_id}"
            )

        record = rows[0]

        # Build enriched ticket information
        enriched = {
            "production_id": production_id,
            "found": True,
            "record": record,
            "suggested_summary": f"Production issue for ID {production_id}",
            "suggested_description": format_record_for_description(record)
        }

        # Try to infer department
        if "department" in record:
            enriched["inferred_project"] = record["department"]

        return ok(data=enriched)

    except Exception as e:
        return fail(str(e))


def format_record_for_description(record):
    """
    Convert database record into readable ticket description.
    """
    lines = ["**Auto-extracted from production database:**", ""]

    priority_fields = [
        "name", "title", "type", "status", "description",
        "severity", "reported_by", "location", "asset_id"
    ]

    for key in priority_fields:
        if key in record and record[key]:
            formatted_key = key.replace("_", " ").title()
            lines.append(f"- **{formatted_key}:** {record[key]}")

    # Add other fields
    other_fields = [
        k for k in record.keys()
        if k not in priority_fields and record[k]
    ]

    if other_fields:
        lines.append("")
        lines.append("**Additional Details:**")
        for key in other_fields:
            formatted_key = key.replace("_", " ").title()
            lines.append(f"- {formatted_key}: {record[key]}")

    return "\n".join(lines)

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

READ_TOOLS = {

    "get_projects": get_projects_tool,
    "get_issue": get_issue_tool,
    "get_users": get_users_tool,
    "get_priorities": get_priorities_tool,
    "get_issue_types": get_issue_types_tool,
    "get_project_fields": get_project_fields_tool,
    "get_sprints": get_sprints_tool,

    "resolve_user": resolve_user_tool,

    "search_issues": search_issues_tool,
    "sprint_closed_tickets": sprint_closed_tickets_tool,
    "workload": workload_tool,

    "route_department": route_department_tool,
    "db_lookup": db_lookup_tool,
    "ask_user": ask_user_tool,

    "database_query": database_query_tool,
    "database_health": database_health_tool,
}