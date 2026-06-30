# Quest LLM Manual

`quest` is a small action-plus-decode subsystem.

When editing:

- preserve the difference between selecting a quest and requesting quest data
- keep async decode helpers thin and explicit
- avoid collapsing quest text helpers into generic decode utilities that belong elsewhere
