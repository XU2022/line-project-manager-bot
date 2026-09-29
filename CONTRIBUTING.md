# Contributing

## Before opening a change

- Do not include real LINE IDs, access tokens, channel secrets, chat logs, or screenshots.
- Use only the placeholder members and groups already present in the tests.
- Keep task behavior independent from any specific business or content type.
- Add or update tests for behavior changes.

## Local checks

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -W error::ResourceWarning -m unittest discover -s tests -v
```

## Security reports

Do not publish production credentials or personal information in an issue. Follow `SECURITY.md` for private reporting guidance.
