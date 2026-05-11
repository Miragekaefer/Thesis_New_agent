# agent.py

import json
import re
import ollama

from config import OLLAMA_MODEL, MAX_AGENT_STEPS
from prompts import SYSTEM_PROMPT
from tools import (
    TOOLS,
    READ_TOOLS,
    PLAN_AND_CREATE_TOOLS,
    WRITE_TOOLS,
)
from memory import AgentMemory


class JiraAgent:
    """
    Multi-step enterprise agent with:
    - tool planning
    - follow-up questions
    - memory
    - unfinished task continuation
    """

    def __init__(self):
        self.memory = AgentMemory()

        self.phase = "PLAN"
        self.proposed_action = None

        self.pending_goal = None

        self.READ_TOOLS = {
            "get_issue",
            "search_issues",
            "workload",
            "get_projects",
            "database_query",
            "database_health",
            "resolve_user",
            "get_users",
            "get_priorities",
            "get_issue_types",
            "get_project_fields",
            "get_sprints",
            "sprint_closed_tickets",
        }

        self.PLANNING_TOOLS = {
            "plan_ticket_creation",
        }

        self.WRITE_TOOLS = {
            "execute_ticket_creation",
        }

    # -------------------------------------------------
    # Helpers
    # -------------------------------------------------

    def _safe_json_parse(self, text):
        """
        Try normal JSON parse first.
        If model adds extra text, extract first {...}
        """
        try:
            return json.loads(text)
        except:
            pass

        match = re.search(r"\{.*\}", text, re.DOTALL)

        if match:
            try:
                return json.loads(match.group(0))
            except:
                return None

        return None



    def _call_llm(self, user_goal):

        prompt = f"""
        User Goal:
        {user_goal}

        Available Tools:
        {list(TOOLS.keys())}

        Read Tools:
        {list(self.READ_TOOLS)}

        Planning Tools:
        {list(self.PLANNING_TOOLS)}

        Write Tools:
        {list(self.WRITE_TOOLS)}

        Previous Tool Results:
        {self.memory.get_history()}
        """

        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
        )

        return response["message"]["content"]

    def _handle_missing_fields(self, result):
        """
        Convert missing_fields into user-friendly question
        """
        fields = result.get("missing_fields", [])

        if not fields:
            return "Please provide more information."

        fields_text = ", ".join(fields)

        return f"Please provide the following information: {fields_text}"

    # -------------------------------------------------
    # Main Agent Loop
    # -------------------------------------------------

    def run(self, user_input):

        # --------------------------
        # CONFIRMATION PHASE
        # --------------------------
        if self.phase == "CONFIRM":

            if user_input.lower() not in ["yes", "y", "confirm", "ok"]:
                self.phase = "PLAN"
                self.proposed_action = None
                return "Cancelled. No ticket was created."

            # EXECUTE
            tool_name = "execute_ticket_creation"

            tool_input = {
                "plan": self.proposed_action["input"]
            }

            result = TOOLS[tool_name]({
                "plan": self.proposed_action["input"]
                })

            self.memory.add(tool=tool_name, tool_input=tool_input, result=result)

            self.phase = "PLAN"
            self.proposed_action = None

            return result

        # --------------------------
        # NORMAL LLM CALL
        # --------------------------
        user_goal = user_input

        for step in range(MAX_AGENT_STEPS):

            raw = self._call_llm(user_goal)
            print("[LLM RAW]:", raw)


            decision = self._safe_json_parse(raw)

            if not decision:
                return "Invalid model output"

            tool_name = decision.get("tool")
            tool_input = decision.get("input", {})

            # -------------------------------------------------
            # UNKNOWN TOOL
            # -------------------------------------------------

            if tool_name not in TOOLS:
                return f"Unknown tool selected: {tool_name}"

            # -------------------------------------------------
            # READ TOOLS
            # -------------------------------------------------

            if tool_name in self.READ_TOOLS:

                result = TOOLS[tool_name](tool_input)

                self.memory.add(
                    tool=tool_name,
                    tool_input=tool_input,
                    result=result
                )

                return result

            # -------------------------------------------------
            # PLANNING TOOLS
            # -------------------------------------------------


            if tool_name in self.PLANNING_TOOLS:

                self.proposed_action = {
                    "tool": "execute_ticket_creation",
                    "input": tool_input
                }

                self.phase = "CONFIRM"

                return {
                    "status": "PENDING_CONFIRMATION",
                    "proposal": tool_input,
                    "message": f"""
            Proposed ticket:

            Project: {tool_input.get('project')}
            Summary: {tool_input.get('summary')}
            Description: {tool_input.get('description')}
            Assignee: {tool_input.get('assignee')}
            Priority: {tool_input.get('priority')}

            Confirm creation? (yes/no)
            """
                }

            # -------------------------------------------------
            # WRITE TOOLS
            # -------------------------------------------------

            if tool_name in self.WRITE_TOOLS:
                return "Write operations require confirmation first."

            return f"Unhandled tool type: {tool_name}"

        return "Max steps reached"