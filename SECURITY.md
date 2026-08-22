# Security Policy

## Reporting

Please report security issues privately through GitHub's security reporting features when available. Do not include secrets, private camera frames, or personal data in public issues.

## Local input control

Ghosty Input intentionally generates local mouse and keyboard events. Keep PyAutoGUI's fail-safe enabled and stop the application before using it in security-sensitive workflows such as password entry or system administration.
