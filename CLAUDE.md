# Groove Log — Instructions for Claude

## Authorship
This is a real product. The user does not write any code — all code is authored by Claude. The user drives product direction, architecture, and technical decisions.

## Architecture & Technical Decisions
Always consult the user before making architecture or technical decisions. This includes:
- Introducing new dependencies or libraries
- Changing data models or database schemas
- Restructuring files or modules
- Choosing between implementation approaches with meaningful trade-offs

Present options with trade-offs and ask for the user's preference.

## Proactive Code Quality
Flag anything that looks off and ask for permission to fix it:
- Leftover code or artifacts from previous sessions (dead code, unused imports, orphaned files)
- Poor design patterns, inconsistencies, or things that don't make sense
- Potential bugs or fragile code spotted while working on nearby areas

Don't silently fix these — call them out so the user can make an informed decision.

## Clarifications
When clarifications are necessary before proceeding, always toggle plan mode. Present your questions and reasoning there, then exit plan mode once alignment is reached and you're ready to implement.

## Testing
Run `make full-test` after any backend change. If there are test failures, fix them — even if the failures are unrelated to the current session's work.
