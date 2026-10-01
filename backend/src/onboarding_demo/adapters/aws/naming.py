"""AgentCore Memory actor ids allow letters, digits, hyphens and underscores, not dots."""
import re


def memory_actor_id(username: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "-", username)
