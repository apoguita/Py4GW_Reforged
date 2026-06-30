# Friend List LLM Manual

`friend_list` is a state-plus-callback subsystem.

Important traits:

- owns runtime friend-list action functions
- hooks friend events to synthesize callback flow
- presents typed counts and convenience methods

When changing it:

- preserve distinction between friend types
- do not break status callback semantics
- keep add/remove/status actions thin wrappers over resolved runtime primitives
