# tools/helpers.py

from jira_api import (
    resolve_user,
    get_projects,
    get_issue_types,
    get_priorities,
)

def ok(data=None, message=None, **extra):
    payload = {"success": True}

    if data is not None:
        payload["data"] = data

    if message:
        payload["message"] = message

    payload.update(extra)

    return payload


def fail(message, **extra):
    payload = {
        "success": False,
        "error": message
    }

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

    if not isinstance(data, dict):
        return default

    for key in keys:
        if key in data and data[key] not in [None, "", []]:
            return data[key]

    return default


def lower_text(value):
    return str(value).strip().lower()


def normalize_project_key(project):

    if not project:
        return project

    return project.strip().upper().replace("-", "")


def normalize_issue_type(raw):

    if not raw:
        return "Task"

    value = lower_text(raw)

    mapping = {
        "task": "Task",
        "story": "Story",
        "bug": "Bug",
        "epic": "Epic",
    }

    return mapping.get(value, raw)