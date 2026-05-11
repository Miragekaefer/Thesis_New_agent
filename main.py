# main.py

import subprocess
import sys

from agent import JiraAgent


# =========================================================
# CONSOLE UI HELPERS
# =========================================================

def print_banner():

    print("=" * 60)
    print(" Jira Multi-Agent Assistant")
    print(" Natural Language -> Tools -> Jira/MySQL")
    print("=" * 60)
    print("Modes:")
    print("  1 - Console Mode")
    print("  2 - Web UI Mode")
    print("=" * 60)
    print()


def print_help():

    print("\nExamples:")
    print("- How many tickets are assigned to John Doe?")
    print("- Create a bug ticket for Production ID 12345")
    print("- How many tickets were closed during Sprint 22?")
    print("- Show latest PA tickets")
    print("- Please create a ticket for this bug")
    print("- Show latest incidents from database")
    print()


# =========================================================
# WEB UI STARTER
# =========================================================

def start_web_ui():

    print("\nStarting Streamlit UI...\n")

    subprocess.run(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "ui.py"
        ]
    )


# =========================================================
# CONSOLE MODE
# =========================================================

def start_console_mode():

    try:
        agent = JiraAgent()

    except Exception as e:
        print("Failed to initialize agent:", e)
        return

    print("Agent ready.\n")

    while True:

        try:
            user_input = input("You: ").strip()

        except KeyboardInterrupt:
            print("\nExiting...")
            break

        except EOFError:
            print("\nExiting...")
            break

        if not user_input:
            continue

        command = user_input.lower()

        # -------------------------------------------------
        # COMMANDS
        # -------------------------------------------------

        if command == "exit":
            print("Goodbye.")
            break

        if command == "reset":

            if hasattr(agent, "reset"):
                agent.reset()

            print("AI: Memory cleared.")
            continue

        if command == "help":
            print_help()
            continue

        # -------------------------------------------------
        # NORMAL AGENT REQUEST
        # -------------------------------------------------

        try:

            answer = agent.run(user_input)

            print(f"\nAI: {answer}\n")

        except Exception as e:

            print(f"\nAI: Unexpected error: {e}\n")


# =========================================================
# MAIN MENU
# =========================================================

def main():

    print_banner()

    mode = input(
        "Select mode (1 = Console, 2 = Web UI): "
    ).strip()

    if mode == "2":
        start_web_ui()

    else:
        start_console_mode()


# =========================================================
# ENTRYPOINT
# =========================================================

if __name__ == "__main__":
    main()