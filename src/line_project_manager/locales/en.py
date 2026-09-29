"""English messages for commands, setup, and reminders."""

STAGE_NAMES = {"planning": "planning", "execution": "execution", "review": "review", "delivery": "delivery"}
STATUS_NAMES = {"open": "in progress", "blocked": "blocked", "completed": "completed", "cancelled": "cancelled"}
UNKNOWN_MEMBER = "You are not a registered project member."
MISSING_NAME = 'Give the task a name, for example: create task "Demo", owner me.'
UNKNOWN_OWNER = "The specified owner is not registered."
INVALID_DUE = "The due date is invalid. Check the date and time."
INCOMPLETE_TASK = "The task information is incomplete. No task was created."
CREATED = "Task created."
NOT_FOUND = "Task {task_id} was not found."
FORBIDDEN = "You do not have permission to modify this task."
NO_CHANGES = "No stage, owner, due date, or status change was recognized."
UPDATED = "Task updated."
STATUS_CHANGED = "Task {status}."
NO_OPEN_TASKS = "There are no active tasks."
TASK_LIST = "Active tasks ({count}):"
MORE_TASKS = "{count} more task(s) not shown."
UNASSIGNED = "unassigned"
SUMMARY = "{task_id} | {name}\nOwner: {owner}; Stage: {stage}; Status: {status}; Due: {due}"
NO_DUE = "not set"
UNKNOWN_OPERATION = "No task operation was recognized. Try create task, update, complete, cancel, or list tasks."
BOOTSTRAP_INFO = "Group ID: {group_id}\nMember ID: {member_id}\nSave these values in the server configuration, then disable bootstrap mode."
BOOTSTRAP_ONLY = 'Bootstrap mode only accepts the "identity" command.'
REMINDER = 'Task {task_id} "{task_name}" is due tomorrow. Please confirm its status.'
