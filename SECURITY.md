# Security Policy

## Supported Versions

Currently, only the latest version of Law7 is supported.

| Version | Supported          |
|---------|-------------------|
| 0.1.x   | :white_check_mark: Yes |

## Reporting a Vulnerability

If you discover a security vulnerability in Law7, please report it responsibly.

**Please DO NOT:**
- Publicly disclose the vulnerability
- Exploit the vulnerability
- Use the vulnerability to access data without permission

**Please DO:**
- Send an email to: legoogmiha@gmail.com
- Include "Security Vulnerability" in the subject line
- Provide details about:
  - The vulnerability description
  - Steps to reproduce (if applicable)
  - Potential impact
  - Suggested fix (if known)

## Response Timeline

- **Initial response**: Within 48 hours
- **Investigation**: Within 1 week
- **Patch**: Based on severity and complexity
- **Public disclosure**: After patch is released

## Security Best Practices

When deploying Law7:

1. **Database Security**
   - Use strong passwords for PostgreSQL
   - Restrict database access to localhost only
   - Enable SSL for database connections in production
   - Regular security updates

2. **API Configuration**
   - Keep API keys in environment variables only
   - Never commit `.env` files to version control
   - Use different API keys for development and production

3. **Network Security**
   - Run services behind a firewall
   - Use Docker networks to isolate services
   - Expose only necessary ports

4. **Dependencies**
   - Regularly update dependencies
   - Review security advisories for dependencies
   - Use `npm audit` and `poetry check` regularly

## Security Features

Law7 includes these security features:

- **Input Validation**: All user inputs are validated before processing
- **SQL Injection Prevention**: Parameterized queries for all database operations
- **Environment Variables**: Sensitive configuration via environment variables only
- **No External API Keys**: Does not require external API keys for operation

## Disclaimer

Law7 provides text information from open sources only. It is NOT designed for:
- Official use in court or government bodies
- Legal advice
- Official legal proceedings

Always verify information with official sources and qualified legal professionals.
