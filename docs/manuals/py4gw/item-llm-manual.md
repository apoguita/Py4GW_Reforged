# Item LLM Manual

`item` is broad and hook-heavy.

It mixes:

- raw item/context aliases
- UI message handling
- item-click hooks
- trade/storage/salvage actions
- async name decoding

When editing:

- preserve the distinction between inventory actions and UI-side callbacks
- keep gold/storage behavior explicit
- avoid hiding network/UI side effects behind harmless-looking getters
