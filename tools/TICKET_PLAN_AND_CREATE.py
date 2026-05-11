from jira_api import (
    resolve_user,
    create_issue
)

from tools.HELPERS import (
    ok,
    fail,
    pick,
    normalize_project_key,
    normalize_issue_type,
)


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

    if isinstance(assignee, str):
        resolved = resolve_user(assignee)
        assignee = {
            "accountId": resolved["accountId"],
            "displayName": resolved.get("displayName")
        }
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
    
PLAN_AND_CREATE_TOOLS = {

"plan_ticket_creation": plan_ticket_tool,

"execute_ticket_creation": execute_ticket_tool,
}