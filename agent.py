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
    - database enrichment
    - similarity checking
    """

    def __init__(self):
        self.memory = AgentMemory()

        self.phase = "PLAN"
        self.proposed_action = None
        self.pending_goal = None
        self.enriched_data = None  # Store database lookup results
        self.similarity_data = None  # Store similarity check results

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
            "db_lookup",
            "check_ticket_similarity",
            "search_documents",
        }

        self.PLANNING_TOOLS = {
            "plan_ticket_creation",
            "plan_ticket_with_similarity",
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

    def _extract_production_id(self, text):
        """
        Detect if user mentions a production ID in their request.
        """
        patterns = [
            r"production\s*(?:id)?[:\s#]*(\d+)",
            r"prod[:\s#]*(\d+)",
            r"productionid[:\s]*(\d+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _enrich_with_database(self, production_id):
        """
        Perform database lookup and store results for ticket creation.
        """
        if not production_id:
            return None

        try:
            result = TOOLS["db_lookup"]({"production_id": production_id})

            if result.get("success") and result.get("data", {}).get("found"):
                self.enriched_data = result.get("data")
                return self.enriched_data

        except Exception as e:
            pass

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
                self.enriched_data = None
                return "Cancelled. No ticket was created."

            # EXECUTE
            tool_name = "execute_ticket_creation"

            # Merge enriched data into plan
            plan_data = self.proposed_action["input"]

            if self.enriched_data:
                if not plan_data.get("description"):
                    plan_data["description"] = self.enriched_data.get(
                        "suggested_description", ""
                    )
                if not plan_data.get("summary"):
                    plan_data["summary"] = self.enriched_data.get(
                        "suggested_summary", ""
                    )

            tool_input = {"plan": plan_data}

            result = TOOLS[tool_name](tool_input)

            self.memory.add(tool=tool_name, tool_input=tool_input, result=result)

            self.phase = "PLAN"
            self.proposed_action = None
            self.enriched_data = None

            return result

        # --------------------------
        # DATABASE ENRICHMENT
        # --------------------------
        production_id = self._extract_production_id(user_input)
        if production_id:
            enrichment = self._enrich_with_database(production_id)
            if enrichment:
                self.memory.add(
                    tool="db_lookup",
                    tool_input={"production_id": production_id},
                    result={"success": True, "data": enrichment}
                )

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

                user_goal = f"""
                Original Question:

                {user_input}

                Retrieved Information:

                {result}

                Using the retrieved information,
                answer the user's original question.
                """

                continue

            # -------------------------------------------------
            # PLANNING TOOLS
            # -------------------------------------------------

            if tool_name in self.PLANNING_TOOLS:

                # Enrich input with database data if available
                if self.enriched_data:
                    if not tool_input.get("description"):
                        tool_input["description"] = self.enriched_data.get(
                            "suggested_description", ""
                        )
                    if tool_input.get("project") is None:
                        tool_input["project"] = self.enriched_data.get(
                            "inferred_project"
                        )

                # Execute planning tool
                result = TOOLS[tool_name](tool_input)

                # Check if result asks for user input
                if result.get("ask_user"):
                    return result

                # Store similarity data if available
                plan_data = result.get("data", {})
                similarity_check = plan_data.get("similarity_check", {})
                if similarity_check:
                    self.similarity_data = similarity_check

                self.proposed_action = {
                    "tool": "execute_ticket_creation",
                    "input": plan_data  # Use enhanced plan data
                }

                self.phase = "CONFIRM"

                # Build confirmation message with warnings
                warnings = []
                if self.enriched_data:
                    warnings.append(
                        "\n**Database enrichment applied:**\n"
                        f"- Production ID: {self.enriched_data.get('production_id')}\n"
                        f"- Data extracted from database and included in description"
                    )

                # Add similarity warnings
                if similarity_check:
                    duplicates = similarity_check.get("potential_duplicates", [])
                    if duplicates:
                        warnings.append(
                            f"\n**Warning: {len(duplicates)} potential duplicate(s) found!**\n"
                            f"- {duplicates[0]['key']}: {duplicates[0]['summary'][:50]}... ({duplicates[0]['similarity']:.0%} similar)\n"
                            f"- Consider updating existing ticket instead."
                        )

                    validation = similarity_check.get("validation_result", {})
                    if validation.get("status") == "warning":
                        warnings.append(f"\n**Validation:** {validation.get('message')}")

                    # Add suggestions if available
                    suggestions = similarity_check.get("suggestions", {}).get("recommendations", [])
                    if suggestions:
                        suggestion_text = "\n**Suggestions from similar tickets:**"
                        for s in suggestions[:3]:
                            suggestion_text += f"\n- {s['field']}: {s['suggested_value']} ({s['reason']})"
                        warnings.append(suggestion_text)

                proposal = plan_data
                warning_text = "\n".join(warnings) if warnings else ""

                return {
                    "status": "PENDING_CONFIRMATION",
                    "proposal": proposal,
                    "similarity_check": similarity_check,
                    "message": f"""
**Proposed ticket:**

**Project:** {proposal.get('project') or 'Auto-detected'}
**Summary:** {proposal.get('summary')}
**Description:** {proposal.get('description', '(none)')[:200]}...
**Assignee:** {proposal.get('assignee', {}).get('displayName') or 'Unassigned'}
**Priority:** {proposal.get('priority', 'Medium')}
**Type:** {proposal.get('issue_type', 'Task')}

{warning_text}

**Confirm creation?** (yes/no)
                    """
                }

            # -------------------------------------------------
            # WRITE TOOLS
            # -------------------------------------------------

            if tool_name in self.WRITE_TOOLS:
                return "Write operations require confirmation first."

            return f"Unhandled tool type: {tool_name}"

        return "Max steps reached"

    def reset(self):
        """Reset agent state."""
        self.memory.clear()
        self.phase = "PLAN"
        self.proposed_action = None
        self.enriched_data = None
        self.similarity_data = None