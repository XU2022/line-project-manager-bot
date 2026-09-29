# Commands

Use a real LINE `@Bot` mention. If mentions are unavailable, use the configured single-letter fallback at the start of the message.

## Create

```text
@Bot create task "Demo task", owner me, due 10-15
@Bot create task "Example review", owner Bob, due 2026-10-20 16:30
```

Quoted names are recommended. A date without a time defaults to 18:00. Numeric dates use `YYYY-MM-DD` or `MM-DD`.

## Update

```text
@Bot update TASK-0001, stage review
@Bot update TASK-0001, owner Alice
@Bot update TASK-0001, due 2026-10-22 12:00
@Bot update TASK-0001, blocked
@Bot update TASK-0001, resume
```

## Complete or cancel

```text
@Bot complete TASK-0001
@Bot cancel TASK-0001
```

## List

```text
@Bot list tasks
@Bot show active tasks
```

Only active tasks are listed. Display names come from the local member configuration.

## Limits

- Parsing is deterministic; ordinary conversation is never sent to a language model.
- Only structured bot mentions or the start-of-message fallback trigger are accepted.
- Members must be registered before using task operations.
- In-group member registration is not included.

