# ui.py

import streamlit as st

from agent import JiraAgent
from mysql_api import test_connection


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="JIRA AI Agent",
    page_icon="🤖",
    layout="wide"
)


# =========================================================
# SESSION STATE
# =========================================================

if "agent" not in st.session_state:
    st.session_state.agent = JiraAgent()

if "messages" not in st.session_state:
    st.session_state.messages = []


# =========================================================
# HEADER
# =========================================================

st.title("JIRA AI Agent")
st.caption("Jira + MySQL + Multi-Tool Assistant")


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.header("Controls")

    # -----------------------------------------------------
    # RESET
    # -----------------------------------------------------

    if st.button("Reset Conversation"):

        st.session_state.messages = []
        st.session_state.agent = JiraAgent()

        st.success("Conversation reset.")

    st.divider()

    # -----------------------------------------------------
    # DATABASE TEST
    # -----------------------------------------------------

    st.subheader("Database")

    if st.button("Test Database Connection"):

        try:

            result = test_connection()

            if result.get("success"):
                st.success(result.get("message"))

            else:
                st.error(result.get("error"))

        except Exception as e:
            st.error(str(e))

    st.divider()

    # -----------------------------------------------------
    # CONNECTED SYSTEMS
    # -----------------------------------------------------

    st.markdown("### Connected Systems")

    st.markdown("- Jira")
    st.markdown("- MySQL")

    st.divider()

    # -----------------------------------------------------
    # EXAMPLES
    # -----------------------------------------------------

    st.markdown("### Example Questions")

    st.markdown(
        """
- Show latest incidents
- How many tickets are assigned to John?
- Create a bug ticket for production issue
- Show PA sprint tickets
- Query production database
        """
    )


# =========================================================
# CHAT HISTORY
# =========================================================

for message in st.session_state.messages:

    with st.chat_message(message["role"]):

        st.markdown(message["content"])


# =========================================================
# USER INPUT
# =========================================================

prompt = st.chat_input("Ask the agent...")


# =========================================================
# MAIN EXECUTION
# =========================================================

if prompt:

    # -----------------------------------------------------
    # STORE USER MESSAGE
    # -----------------------------------------------------

    st.session_state.messages.append(
        {
            "role": "user",
            "content": prompt
        }
    )

    # -----------------------------------------------------
    # DISPLAY USER MESSAGE
    # -----------------------------------------------------

    with st.chat_message("user"):

        st.markdown(prompt)

    # -----------------------------------------------------
    # ASSISTANT RESPONSE
    # -----------------------------------------------------

    with st.chat_message("assistant"):

        with st.spinner("Thinking..."):

            try:

                result = st.session_state.agent.run(prompt)

                # -------------------------------------------------
                # HANDLE DICTIONARY RESPONSES
                # -------------------------------------------------

                if isinstance(result, dict):

                    # Confirmation workflow
                    if result.get("status") == "PENDING_CONFIRMATION":

                        proposal = result.get("proposal", {})

                        response_text = (
                            "### Pending Confirmation\n\n"
                            f"**Project:** {proposal.get('project')}\n\n"
                            f"**Summary:**\n{proposal.get('summary')}\n\n"
                            f"**Description:**\n{proposal.get('description')}\n\n"
                            f"**Assignee:**\n{proposal.get('assignee')}\n\n"
                            "Type:\n"
                            "- yes\n"
                            "- confirm\n"
                            "- ok\n\n"
                            "to execute the action."
                        )

                    else:

                        response_text = str(result)

                else:

                    response_text = str(result)

            except Exception as e:

                response_text = f"Unexpected error: {str(e)}"

            # -------------------------------------------------
            # DISPLAY RESPONSE
            # -------------------------------------------------

            st.markdown(response_text)

    # -----------------------------------------------------
    # STORE ASSISTANT RESPONSE
    # -----------------------------------------------------

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": response_text
        }
    )