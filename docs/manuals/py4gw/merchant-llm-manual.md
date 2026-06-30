# Merchant LLM Manual

`merchant` is a narrow transaction subsystem with explicit packet shapes.

When editing:

- preserve the `TransactionType`, `TransactionInfo`, and `QuoteInfo` model
- keep quote and transact paths separate
- do not blur merchant action methods with general item logic already owned by `item`
