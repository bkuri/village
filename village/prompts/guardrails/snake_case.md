---
id: guardrails/snake_case
desc: Enforce snake_case naming for all source files.
priority: 100
tags: [convention:naming]
---

## Filename Casing Guardrails

- **ALL source files MUST use `snake_case` naming** — lowercase letters, digits, and underscores only.
- **Do NOT create files with:**
  - CamelCase (`MyFile.go`, `userProfile.ts`)
  - kebab-case (`my-file.go`, `user-profile.ts`)
  - Mixed case (`myFile.go`, `USERFile.go`)
  - Spaces or special characters
- **Valid examples:** `user_profile.go`, `rate_limiter.py`, `test_utils.ts`, `config_2025.yaml`
- **Invalid examples:** `userProfile.go`, `UserProfile.go`, `user-profile.go`, `user profile.go`
- **Exception:** Files with a well-established upstream convention (e.g., `Dockerfile`, `Makefile`, `CMakeLists.txt`, `.gitignore`) are permitted.
- **Exception:** Files inside `vendor/`, `node_modules/`, or other third-party directories.

This policy is enforced by post-hoc filename scan at commit time. Violations block the commit.
