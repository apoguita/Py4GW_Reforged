# Context Family LLM Manual

The `include/GW/context` family is the repository's raw game-state model.

Think of it as:

- structure definitions
- array/list/type aliases
- context root layouts

Not as:

- action methods
- policy layers
- hook dispatch surfaces

Important modeling rule:

- managers should build behavior on top of these types
- context headers should remain primarily declarative and layout-oriented

When changing the context family:

- preserve separation between root contexts and convenience managers
- be careful with binary layout assumptions and static-size expectations
- avoid adding manager-style helpers directly into raw layout headers unless the repository already treats that header as mixed-purpose

Use the family to reason about what data exists. Use manager manuals to reason about how the code acts on that data.
