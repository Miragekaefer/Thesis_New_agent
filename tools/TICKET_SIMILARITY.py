# tools/TICKET_SIMILARITY.py
"""
Ticket Similarity Tool

Compares planned tickets with existing Jira tickets to:
- Validate ticket quality
- Detect potential duplicates
- Suggest improvements from similar resolved tickets
- Recommend better field values
"""

import re
from datetime import datetime, timedelta
from jira_api import search_issues, get_issue
from tools.HELPERS import ok, fail, ask, pick


def extract_keywords(text):
    """
    Extract meaningful keywords from text.
    Filters out common words and keeps significant terms.
    """
    if not text:
        return set()

    # Convert to lowercase and extract words
    text = text.lower()

    # Remove special characters but keep spaces
    text = re.sub(r'[^a-z0-9\s]', ' ', text)

    # Split into words
    words = text.split()

    # Stop words to ignore
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at',
        'to', 'for', 'of', 'with', 'by', 'from', 'is', 'are',
        'was', 'were', 'been', 'be', 'have', 'has', 'had', 'do',
        'does', 'did', 'will', 'would', 'could', 'should', 'may',
        'might', 'must', 'shall', 'can', 'this', 'that', 'these',
        'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they',
        'what', 'which', 'who', 'when', 'where', 'why', 'how',
        'all', 'each', 'every', 'both', 'few', 'more', 'most',
        'other', 'some', 'such', 'no', 'nor', 'not', 'only',
        'own', 'same', 'so', 'than', 'too', 'very', 'just',
    }

    # Filter out stop words and short words
    keywords = {
        word for word in words
        if word not in stop_words and len(word) > 2
    }

    return keywords


def calculate_similarity(text1, text2):
    """
    Calculate Jaccard similarity between two texts.
    Returns score between 0 (no match) and 1 (perfect match).
    """
    if not text1 or not text2:
        return 0.0

    keywords1 = extract_keywords(text1)
    keywords2 = extract_keywords(text2)

    if not keywords1 or not keywords2:
        return 0.0

    # Jaccard similarity: intersection / union
    intersection = keywords1 & keywords2
    union = keywords1 | keywords2

    similarity = len(intersection) / len(union)

    return similarity


def search_similar_tickets(project, summary, description=None, max_results=10):
    """
    Search Jira for tickets similar to the planned one.
    """
    if not project or not summary:
        return []

    # Build JQL query
    jql_parts = [f'project = "{project}"']

    # Extract keywords from summary
    summary_keywords = extract_keywords(summary)
    if summary_keywords:
        # Search for any of the main keywords in summary
        main_keywords = list(summary_keywords)[:5]  # Limit to top 5
        keyword_jql = ' OR '.join([f'summary ~ "{kw}"' for kw in main_keywords])
        jql_parts.append(f'({keyword_jql})')

    jql = ' AND '.join(jql_parts)

    try:
        result = search_issues(jql)
        issues = result.get("issues", [])

        # Calculate similarity scores
        scored_issues = []
        for issue in issues:
            fields = issue.get("fields", {})
            existing_summary = fields.get("summary", "")
            existing_description = fields.get("description", "") or ""

            # Calculate similarity scores
            summary_similarity = calculate_similarity(summary, existing_summary)
            desc_similarity = calculate_similarity(description or "", existing_description)

            # Combined score (weight summary more)
            combined_score = (summary_similarity * 0.7) + (desc_similarity * 0.3)

            scored_issues.append({
                "key": issue.get("key"),
                "summary": existing_summary,
                "status": fields.get("status", {}).get("name"),
                "priority": fields.get("priority", {}).get("name"),
                "issue_type": fields.get("issuetype", {}).get("name"),
                "assignee": (fields.get("assignee") or {}).get("displayName"),
                "created": fields.get("created"),
                "resolution": fields.get("resolutiondate"),
                "description_preview": (existing_description[:150] + '...') if len(existing_description) > 150 else existing_description,
                "similarity_score": round(combined_score, 2),
                "summary_similarity": round(summary_similarity, 2)
            })

        # Sort by similarity score
        scored_issues.sort(key=lambda x: x["similarity_score"], reverse=True)

        return scored_issues[:max_results]

    except Exception as e:
        return []


def detect_duplicates(new_ticket, existing_tickets, threshold=0.6):
    """
    Identify potential duplicates from existing tickets.
    Threshold: 0.6 = 60% similarity
    """
    duplicates = []

    for ticket in existing_tickets:
        if ticket["similarity_score"] >= threshold:
            duplicates.append({
                "key": ticket["key"],
                "summary": ticket["summary"],
                "status": ticket["status"],
                "similarity": ticket["similarity_score"],
                "reason": f"{int(ticket['similarity_score'] * 100)}% similar summary"
            })

    return duplicates


def learn_from_resolved_tickets(similar_tickets, threshold=0.4):
    """
    Extract learnings from similar resolved tickets.
    Suggests improvements for the new ticket.
    """
    suggestions = {
        "common_priorities": {},
        "common_issue_types": {},
        "frequent_assignees": {},
        "description_patterns": [],
        "resolution_insights": []
    }

    # Filter for resolved/done tickets with good similarity
    resolved_similar = [
        t for t in similar_tickets
        if t["status"] in ["Done", "Closed", "Resolved"]
        and t["similarity_score"] >= threshold
    ]

    if not resolved_similar:
        return None

    # Analyze patterns
    for ticket in resolved_similar:
        # Priority patterns
        priority = ticket.get("priority")
        if priority:
            suggestions["common_priorities"][priority] = \
                suggestions["common_priorities"].get(priority, 0) + 1

        # Issue type patterns
        issue_type = ticket.get("issue_type")
        if issue_type:
            suggestions["common_issue_types"][issue_type] = \
                suggestions["common_issue_types"].get(issue_type, 0) + 1

        # Assignee patterns
        assignee = ticket.get("assignee")
        if assignee:
            suggestions["frequent_assignees"][assignee] = \
                suggestions["frequent_assignees"].get(assignee, 0) + 1

    # Generate recommendations
    recommendations = []

    # Priority recommendation
    if suggestions["common_priorities"]:
        top_priority = max(
            suggestions["common_priorities"].items(),
            key=lambda x: x[1]
        )
        recommendations.append({
            "field": "priority",
            "suggested_value": top_priority[0],
            "reason": f"Used in {top_priority[1]} similar resolved tickets"
        })

    # Issue type recommendation
    if suggestions["common_issue_types"]:
        top_type = max(
            suggestions["common_issue_types"].items(),
            key=lambda x: x[1]
        )
        recommendations.append({
            "field": "issue_type",
            "suggested_value": top_type[0],
            "reason": f"Used in {top_type[1]} similar resolved tickets"
        })

    # Assignee suggestion
    if suggestions["frequent_assignees"]:
        top_assignee = max(
            suggestions["frequent_assignees"].items(),
            key=lambda x: x[1]
        )
        recommendations.append({
            "field": "assignee",
            "suggested_value": top_assignee[0],
            "reason": f"Resolved {top_assignee[1]} similar tickets"
        })

    return {
        "recommendations": recommendations,
        "based_on_count": len(resolved_similar),
        "confidence": "high" if len(resolved_similar) >= 3 else "medium"
    }


# =========================================================
# MAIN TOOL FUNCTION
# =========================================================

def check_ticket_similarity_tool(input_data):
    """
    Compare planned ticket with existing Jira tickets.

    INPUT:
    - project (required)
    - summary (required)
    - description (optional)
    - max_results (optional, default 10)

    OUTPUT:
    - similar_tickets: list of matching tickets
    - potential_duplicates: high-similarity matches
    - suggestions: improvements from resolved tickets
    - validation_result: overall assessment
    """

    project = pick(input_data, "project", "projectKey")
    summary = pick(input_data, "summary", "title")
    description = pick(input_data, "description", default="")
    max_results = pick(input_data, "max_results", default=10)

    # Validation
    if not project:
        return ask("Which project should I compare against?", ["project"])

    if not summary:
        return ask("What is the summary/title of the ticket to compare?", ["summary"])

    # Search for similar tickets
    similar_tickets = search_similar_tickets(
        project=project,
        summary=summary,
        description=description,
        max_results=max_results
    )

    if not similar_tickets:
        return ok(
            data={
                "similar_tickets": [],
                "potential_duplicates": [],
                "suggestions": None,
                "validation_result": {
                    "status": "unique",
                    "message": "No similar tickets found. This appears to be a new issue.",
                    "confidence": "high"
                }
            },
            message="Ticket is unique - no similar issues found in Jira."
        )

    # Detect potential duplicates
    duplicates = detect_duplicates(
        new_ticket={"summary": summary, "description": description},
        existing_tickets=similar_tickets,
        threshold=0.6
    )

    # Learn from resolved tickets
    suggestions = learn_from_resolved_tickets(
        similar_tickets,
        threshold=0.4
    )

    # Determine validation result
    if duplicates:
        validation_result = {
            "status": "warning",
            "message": f"Found {len(duplicates)} potential duplicate(s). Review before creating.",
            "confidence": "high"
        }
    elif len(similar_tickets) >= 3:
        validation_result = {
            "status": "info",
            "message": f"Found {len(similar_tickets)} similar tickets. Recommendations available.",
            "confidence": "medium"
        }
    else:
        validation_result = {
            "status": "ok",
            "message": "Similar tickets found but no duplicates detected.",
            "confidence": "high"
        }

    # Build response
    response_data = {
        "similar_tickets": similar_tickets[:5],  # Top 5 for display
        "total_found": len(similar_tickets),
        "potential_duplicates": duplicates,
        "suggestions": suggestions,
        "validation_result": validation_result,
        "project": project,
        "analyzed_summary": summary
    }

    # Add action recommendations
    if duplicates:
        response_data["recommended_action"] = {
            "action": "review_duplicates",
            "message": f"Review {len(duplicates)} potential duplicate(s) before proceeding. " +
                      "Consider updating existing ticket instead of creating a new one."
        }
    elif suggestions:
        response_data["recommended_action"] = {
            "action": "apply_suggestions",
            "message": "Consider applying suggestions from similar resolved tickets to improve ticket quality."
        }

    return ok(
        data=response_data,
        message=f"Found {len(similar_tickets)} similar tickets. " +
               (f"{len(duplicates)} potential duplicate(s) detected." if duplicates else "")
    )


# =========================================================
# TOOL REGISTRY
# =========================================================

SIMILARITY_TOOLS = {
    "check_ticket_similarity": check_ticket_similarity_tool,
}
