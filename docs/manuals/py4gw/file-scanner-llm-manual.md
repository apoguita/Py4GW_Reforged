# FileScanner LLM Manual

`FileScanner` is infrastructure, not a convenience layer.

Its job is:

- map a PE image safely
- validate PE structure
- expose section ranges
- search byte patterns and assertion anchors inside the file image

Critical constraints from `src/base/file_scanner.cpp`:

- x86 only
- relies on PE header layout being valid
- assertion scanning has legacy behavior around file name casing and line-number matching

Do not casually rewrite:

- the assertion search shape
- section detection
- reverse-range support in `FindInRange()`

If you change this subsystem, verify that `Scanner` translation still produces correct live addresses.
