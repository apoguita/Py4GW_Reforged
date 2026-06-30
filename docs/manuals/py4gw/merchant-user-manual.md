# Merchant User Manual

`GW::merchant` handles merchant quote and transaction flows.

Main API:

- `TransactItems(...)`
- `RequestQuote(...)`

It also exposes transaction and quote packet structures for manager-side and hook-side integration.

Use it for merchant trading rather than manually emitting merchant UI messages.
