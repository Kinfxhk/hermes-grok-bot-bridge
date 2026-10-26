TASK = {
    "name": "grok_bot_task",
    "description": (
        "Send a task to a Grok Bot and return immediately with a job id. "
        "The Bot works on its cloud computer. When it posts the result back, "
        "that result is injected into this same chat for you to summarise. "
        "Do not wait or poll in this turn. Use for work the chat model should not do itself."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": "What the Grok Bot should do, in one clear brief."},
            "bot": {"type": "string", "description": "Bot name. Default Boss."},
        },
        "required": ["task"],
        "additionalProperties": False,
    },
}

JOB = {
    "name": "grok_bot_job",
    "description": "Read one Grok Bot job by id. Does not include the callback token.",
    "parameters": {
        "type": "object",
        "properties": {
            "job_id": {"type": "string", "description": "Job id returned by grok_bot_task."},
        },
        "required": ["job_id"],
        "additionalProperties": False,
    },
}
