# FileScanner User Manual

`PY4GW::FileScanner` scans a PE image from disk rather than scanning process memory directly.

Main API in `include/base/file_scanner.h`:

- `CreateFromPath(...)`
- `GetSectionAddressRange(...)`
- `FindAssertion(...)`
- `FindInRange(...)`
- `Find(...)`

What it is used for:

- section-bounded byte scanning
- assertion-string based scan anchors
- disk-image support for runtime scanning through `Scanner`

Important behavior:

- it expects a 32-bit PE image
- it maps the file with `SEC_IMAGE_NO_EXECUTE`
- it records section ranges for `.text`, `.rdata`, and `.data`

Use it when you need to scan a module image by path. Most code should go through `Scanner`, not `FileScanner`, unless it is doing low-level scan infrastructure work.
