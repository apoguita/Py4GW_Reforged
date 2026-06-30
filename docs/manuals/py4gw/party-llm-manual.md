# Party LLM Manual

`party` is action-dense and mixes several domains:

- party state
- hero state
- pet state
- UI callback behavior
- party search flow

When editing:

- preserve existing naming even where the API is older-style lowercase
- keep hero-agent and hero-index semantics distinct
- avoid mixing party-search logic into core party-state helpers
