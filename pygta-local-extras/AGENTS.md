# Package Guidelines

Use this file for the short package-local rules. Use
[../CONTRIBUTING.md](../CONTRIBUTING.md) for workspace workflows and placement, and
[../CODING_GUIDELINES.md](../CODING_GUIDELINES.md) for style.

- [pygta-local-extras](.) is the default home for reusable helpers shared across workspace projects but not yet ready for upstream.
- Keep the public API small and re-export only stable helpers from `src/__init__.py`.
- Add new code to existing subpackages before creating new ones.
- Update package mappings in [pyproject.toml](pyproject.toml) if you add a new subpackage.
