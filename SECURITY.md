# Security Policy

## Sensitive information

Do not commit any of the following:

- LINE channel secrets or access tokens
- LINE user, group, or room identifiers from a real deployment
- Runtime databases and event logs
- Private domain names, IP addresses, or server account details
- Screenshots containing real accounts, conversations, or project information

Use `.env.example` and the files under `config/` only as templates. Replace placeholders in local files that remain outside Git.

## Reporting a vulnerability

Do not include production credentials or personal data in a public issue. Contact the repository owner privately before sharing sensitive reproduction details.
