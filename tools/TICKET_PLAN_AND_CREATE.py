from jira_api import (
    resolve_user,
    create_issue
)

from tools.HELPERS import (
    ok,
    fail,
    ask,
    pick,
    normalize_project_key,
    normalize_issue_type,
)

import re


PROJECT_ROUTING = {
    "PA": {
        "name": "Production Analytics",
        "aliases": [
            "pa",
            "production analytics",
        ],
        "keywords": {
            "powerbi": 5,
            "power bi": 5,
            "analysis": 3,
            "analytics": 4,
            "dashboard": 4,
            "report": 3,
            "reporting": 3,
            "kpi": 2,
            "metric": 2,
            "tableau": 3,
            "data": 1,
            "etl": 2,
        }
    },

    "IT": {
        "name": "IT Support",
        "aliases": [
            "it",
            "helpdesk",
            "support",
        ],
        "keywords": {
            "login": 4,
            "password": 4,
            "vpn": 5,
            "access": 3,
            "permission": 3,
            "account": 2,
            "email": 2,
            "outlook": 3,
            "laptop": 2,
        }
    },

    "WEB": {
        "name": "Web Team",
        "aliases": [
            "web",
            "website team",
        ],
        "keywords": {
            "website": 5,
            "web": 3,
            "browser": 2,
            "frontend": 3,
            "page": 2,
            "portal": 2,
            "ui": 1,
        }
    },

    "DB": {
        "name": "Database Team",
        "aliases": [
            "db",
            "database",
        ],
        "keywords": {
            "sql": 5,
            "mysql": 5,
            "postgres": 4,
            "database": 4,
            "query": 2,
            "server": 2,
        }
    },

    "QA": {
        "name": "Quality Assurance",
        "aliases": [
            "qa",
            "quality assurance",
        ],
        "keywords": {
            "bug": 4,
            "crash": 5,
            "broken": 4,
            "broke": 4,
            "error": 3,
            "not working": 5,
            "issue": 1,
        }
    }
}

def normalize_text(text: str) -> str:
    """
    Normalize user input before routing.
    """

    t = text.lower()

    replacements = {
        "power bi": "powerbi",
        "pwbi": "powerbi",
        "analyse": "analysis",
        "analytic": "analytics",
    }

    for src, target in replacements.items():
        t = t.replace(src, target)

    return t

def infer_department_from_text(text):
    """
    Determine best Jira project using:
    1. Explicit department mentions
    2. Weighted keyword ranking
    3. Confidence scoring
    """

    if not text:
        return None

    t = normalize_text(text)

    # =====================================================
    # STEP 1 — EXPLICIT DEPARTMENT MENTION ALWAYS WINS
    # =====================================================

    for project_key, config in PROJECT_ROUTING.items():

        aliases = config.get("aliases", [])

        for alias in aliases:

            pattern = r"\b" + re.escape(alias.lower()) + r"\b"

            if re.search(pattern, t):
                return {
                    "project": project_key,
                    "confidence": 999,
                    "reason": f"Explicit department mention: {alias}"
                }

    # =====================================================
    # STEP 2 — WEIGHTED KEYWORD SCORING
    # =====================================================

    print("\n[ROUTING DEBUG]")
    print("Input text:", t)

    scores = {}

    for project_key, config in PROJECT_ROUTING.items():

        keywords = config.get("keywords", {})

        total_score = 0
        matched_keywords = []

        for keyword, weight in keywords.items():

            if keyword in t:
                total_score += weight
                matched_keywords.append(f"{keyword}(+{weight})")

        print(
            f"[ROUTING] {project_key} "
            f"score={total_score} "
            f"matches={matched_keywords}"
        )

        if total_score > 0:
            scores[project_key] = {
                "score": total_score,
                "matched": matched_keywords
            }

    print("[ROUTING] Final scores:", scores)

    # =====================================================
    # STEP 3 — NO MATCH
    # =====================================================

    if not scores:
        return None

    # =====================================================
    # STEP 4 — BEST MATCH
    # =====================================================

    best_project = max(
        scores,
        key=lambda p: scores[p]["score"]
    )

    best_score = scores[best_project]["score"]

    print(
    f"[ROUTING] WINNER: {best_project} "
    f"(score={best_score})"
    )

    return {
        "project": best_project,
        "confidence": best_score,
        "matched_keywords": scores[best_project]["matched"],
        "reason": "Keyword ranking"
    }



def plan_ticket_tool(input_data):
    """
    Step 1: Build a complete ticket plan.
    NO Jira writes allowed.
    Can auto-infer project from context if missing.
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

    # Try to auto-infer department if project missing
    inferred_project = None

    if not project:
        print("\n[PLAN DEBUG]") #DEBUG
        print("Initial project:", project) #DEBUG
        print("Summary:", summary) #DEBUG
        print("Description:", description) #DEBUG

        combined_text = f"{summary} {description}"

        routing = infer_department_from_text(combined_text)

        if routing:

            inferred_project = routing

            confidence = routing.get("confidence", 0)

            # High confidence auto-routing
            if confidence >= 3:
                project = routing["project"]

            # Low confidence -> ask user
            else:
                return ask(
                    "I could not confidently determine the correct department. "
                    "Which project should this ticket go to?",
                    missing_fields=["project"]
                )

    # Resolve user immediately (but still no execution)
    assignee_id = None
    assignee_display = None
    print("[PLAN DEBUG] Final assigned project:", project) #DEBUG

    if assignee_raw:
        try:
            user = resolve_user(assignee_raw)
        except:
            user = None
        if user:
            assignee_id = user.get("accountId")
            assignee_display = user.get("displayName")
        else:
            warnings.append(
                f"Could not resolve assignee '{assignee_raw}'. Ticket will be unassigned."
            )

    # Build missing fields list with smart messaging
    required_missing = []
    optional_missing = []
    warnings = []

    if not project:
        required_missing.append("project")
    elif inferred_project:
        warnings.append(
            f"Project auto-inferred as '{project}' "
            f"(confidence={inferred_project.get('confidence')}, "
            f"matched={inferred_project.get('matched_keywords', [])})"
        )

    if not summary:
        required_missing.append("summary")

    if not assignee_id:
        optional_missing.append("assignee")
        warnings.append("No assignee specified - ticket will be unassigned")

    # If critical fields missing, ask user directly
    if required_missing:
        questions = {
            "project": "Which department should this ticket go to? (e.g., IT, WEB, PA, PRINT)",
            "summary": "What should be the ticket title/summary?"
        }

        question_text = "Please provide the following required information:\n"
        for field in required_missing:
            question_text += f"\n- {field.capitalize()}: {questions.get(field, 'Please specify')}"

        return ask(question_text, missing_fields=required_missing + optional_missing)

    # Ready to proceed (maybe with warnings)
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
            "ready_to_execute": bool(project and summary),
            "missing_fields": optional_missing,
            "warnings": warnings,
            "auto_inferred": inferred_project is not None
        },
        message="Ticket plan created. Requires confirmation before execution."
    )

def plan_ticket_with_similarity_tool(input_data):
    """
    Enhanced ticket planning with similarity checking.
    Compares planned ticket against existing Jira tickets
    and provides validation + recommendations.
    """
    # First, create the base plan
    base_plan_result = plan_ticket_tool(input_data)

    if not base_plan_result.get("success"):
        return base_plan_result

    if base_plan_result.get("ask_user"):
        return base_plan_result

    plan_data = base_plan_result.get("data", {})

    # Import similarity tool
    from tools.TICKET_SIMILARITY import check_ticket_similarity_tool

    # Check similarity
    similarity_result = check_ticket_similarity_tool({
        "project": plan_data.get("project"),
        "summary": plan_data.get("summary"),
        "description": plan_data.get("description")
    })

    # Merge results
    enhanced_plan = plan_data.copy()
    enhanced_plan["similarity_check"] = similarity_result.get("data", {})

    # Add validation status
    validation = similarity_result.get("data", {}).get("validation_result", {})
    enhanced_plan["validation_status"] = validation.get("status", "ok")
    enhanced_plan["validation_message"] = validation.get("message", "")

    # Add warnings for duplicates
    duplicates = similarity_result.get("data", {}).get("potential_duplicates", [])
    if duplicates:
        if "warnings" not in enhanced_plan:
            enhanced_plan["warnings"] = []
        enhanced_plan["warnings"].append(
            f"Potential duplicate detected: {duplicates[0]['key']} ({duplicates[0]['similarity']:.0%} similar)"
        )

    # Add suggestions if available
    suggestions = similarity_result.get("data", {}).get("suggestions")
    if suggestions:
        enhanced_plan["suggestions"] = suggestions.get("recommendations", [])

    return ok(
        data=enhanced_plan,
        message="Ticket plan created with similarity validation. " +
               (f"Warning: {len(duplicates)} potential duplicate(s) found." if duplicates else "No duplicates detected.")
    )

def execute_ticket_tool(input_data):
    """
    Step 2: Executes a previously planned ticket.
    HARD REQUIREMENT: must receive a full validated plan.
    Assignee is optional - can create unassigned tickets.
    """

    plan = pick(input_data, "plan")

    if not plan:
        return fail("Missing plan. You must call plan_ticket first.")

    project = normalize_project_key(plan.get("project"))
    summary = plan.get("summary")
    description = plan.get("description", "")
    issue_type = plan.get("issue_type", "Task")

    assignee_data = plan.get("assignee", {})

    if isinstance(assignee_data, str):
        try:
            resolved = resolve_user(assignee_data)
            assignee_id = resolved.get("accountId")
        except:
            assignee_id = None
    elif isinstance(assignee_data, dict):
        assignee_id = assignee_data.get("accountId")
    else:
        assignee_id = None

    # HARD SAFETY GATE - only project and summary required
    if not project or not summary:
        return fail("Invalid plan: missing required fields (project or summary)")

    # FINAL EXECUTION - assignee is optional
    try:
        result = create_issue(
            project_key=project,
            summary=summary,
            description=description,
            issue_type=issue_type,
            assignee=assignee_id  # Can be None for unassigned tickets
        )

        message = "Ticket created successfully from approved plan."
        if not assignee_id:
            message += " (Unassigned)"

        return ok(
            data=result,
            message=message,
            meta={
                "project": project,
                "issue_type": issue_type,
                "assigned": assignee_id is not None
            }
        )

    except Exception as e:
        return fail(str(e))
    
PLAN_AND_CREATE_TOOLS = {

"plan_ticket_creation": plan_ticket_tool,

"execute_ticket_creation": execute_ticket_tool,
}