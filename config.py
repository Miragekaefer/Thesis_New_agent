import os
from dotenv import load_dotenv

load_dotenv()

JIRA_URL = os.getenv("JIRA_URL")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_TOKEN = os.getenv("JIRA_TOKEN")

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

MAX_AGENT_STEPS = 6
JIRA_MAX_RESULTS = 10
REQUEST_TIMEOUT = 20