#Enables multi-step reasoning
class AgentMemory:
    def __init__(self):
        self.steps = []

    def add(self, tool, tool_input, result):
        self.steps.append({
            "tool": tool,
            "input": tool_input,
            "result": result
        })

    def get_history(self):
        return self.steps

    def clear(self):
        self.steps = []

    def last_result(self):
        if not self.steps:
            return None
        return self.steps[-1]["result"]

    def __str__(self):
        return str(self.steps)