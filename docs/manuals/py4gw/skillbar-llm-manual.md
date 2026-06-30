# Skillbar LLM Manual

`skillbar` spans three related domains:

- runtime use-skill actions
- template encode/decode
- attribute/profession loading

When editing:

- keep template logic deterministic
- preserve the separation between immediate skill use and build-loading flows
- remember that UI-message integration is part of the public behavior for some load paths
