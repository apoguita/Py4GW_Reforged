# 02 — Encoded Strings (decode engine + byte builder)

The encoded-string system is the **display** channel (see README). It is *not* where mods
come from, but the current Python mod system leans on it heavily to render human-readable
names and tooltips — so it's part of the item-mod story. There are two halves:

- **Decoder** — `Py4GWCoreLib/native_src/internals/string_table.py` (encoded → text).
- **Builder** — `Py4GWCoreLib/native_src/internals/encoded_strings.py` (text/stats → encoded bytes).

This is the "native module where enc strings are decoded and translated" — it's pure
Python, but it re-implements the game's own string-table machinery against `gw.dat`.

## 1. Where encoded bytes come from

Raw `uint16` (wchar) arrays exposed by the C++ bindings as `List[int]`
(`stubs/PyItem.pyi:98-101`):

- `GetInfoString()` — item info string (encoded)
- `GetNameEnc()` — item name (encoded)
- `GetCompleteNameEnc()` — name **with** color, quantity, prefix/suffix markup (encoded)
- `GetSingleItemName()` — bare single-item name, color, no quantity (encoded)

Agents use `PyAgent.get_agent_enc_name(agent_id) -> List[int]` (`stubs/PyAgent.pyi:70`);
the `Agent.py` facade wraps it (`GetEncNameByID`, `GetEncNameStrByID` — `Agent.py:156-162`).

**These are independent of `item.modifiers`.** The encoded name encodes display/markup;
gameplay stats come from the mod list.

## 2. The decoder — `string_table.py`

The module header (`string_table.py:1-24`) documents the full pipeline. In brief:

1. **Codepoint parse** (`_parse_codepoints`, `:44-79`) — an encoded string is a `uint16`
   array encoding a `(table_index, encryption_key)` pair in variable-length base-`0x7F00`
   (`_BASE=0x0100`, `_MORE=0x8000`, `_RANGE=0x7F00`).
2. **String table** (`_string_table: dict[int, bytes]`, ~100K entries per language) is
   loaded once from `gw.dat` on the game thread (`load_string_table` / `_do_load_string_table`,
   `:719-753`), pulling file slots from `TextParser` and reading dat files via
   `read_dat_file_by_hash`.
3. **Entry decode** (`_decode_entry`, `:122-196`) — each entry is
   `[u16 size | u16 base_char | u8 bits_per_char | u8 flags | payload]`. If the key is
   non-zero, a **custom game hash** derives a 20-byte **RC4** key, RC4-decrypts the payload
   (backend = Windows CNG `bcrypt.dll`, pure-Python `_rc4_python` fallback — `:774-826`),
   then **bit-unpacks** characters (special case `base_char=0, bpc=16` ⇒ raw UTF-16LE).
4. **Player names** bypass everything: prefix `0xBA9` + inline ASCII (`:885, 898-906`).
5. **Formatted strings** (item names with prefix/suffix/quantity) use inline arg tags
   `0x0101–0x0109` (numbers) and `0x010A–0x011F` (strings), parsed into a tree
   (`_decode_formatted_tree` / `_decode_formatted_stream`, `:503-653`). `%str1%` / `%num1%`
   placeholders and `[pl:"…"]` plural markers resolve in postprocessing.

**Public API:**
- `decode(raw: bytes, language=None) -> str` (`:888`) — **async**: returns `""` immediately,
  submits the decode to a 1-worker thread pool, caches the result, hits on the next frame.
- `decode_plain(raw, language=None) -> str` (`:942`) — strips color tags / num placeholders.
- `load_string_table(language=0)` (`:739`), `switch_language(language)` (`:763`).

> **Consequence for callers:** name/tooltip text is *not* available synchronously the first
> time you ask. First call warms the cache; the value appears a frame later. Any UI over
> mods has to tolerate a one-frame `""`.

A near-duplicate, slightly older copy lives at `Sources/frenkeyLib/Core/encoded_names.py`
(adds an `ItemName` facade with structured `ItemNameParts(markdown, prefix, item_name,
suffix, num, singular, plural)` extraction and per-language part ordering). The core lib
does **not** import that copy.

## 3. The builder — `encoded_strings.py`

The inverse direction: hand-assemble encoded byte sequences so that GW's own decoder (via
`string_table.decode`) renders a tooltip line. Two classes:

- **`GWStringEncoded`** (`:12`) — wraps `(encoded_bytes, fallback_string)` and exposes
  cached rendered forms: `.plain`, `.full`, `.bonuses_only`, `.singular`, `.plain_singular`,
  plus `decode()`, `decode_with_amount(amount, …)`, `with_amount()`,
  `combine_encoded_strings()`. The `fallback` is returned when decode yields empty (e.g.
  string table not yet loaded).
- **`GWEncoded`** (`:215`) — a large library of raw byte templates and helpers used to build
  those sequences:
  - Rarity color tags: `ITEM_BONUS`, `ITEM_UNCOMMON`, `ITEM_RARE`, `ITEM_UNIQUE`, `ITEM_ENHANCE`, …
  - Per-`ItemType` mod-name fragments: `WEAPON_PREFIXES`, `WEAPON_SUFFIXES` (e.g. "Sword Hilt", "Axe Grip").
  - Per-`ItemBaneSpecies`: `SLAYING_SUFFIXES`, `SPECIES`. Per-`Profession`: `PROFESSION`, `THE_PROFESSION`.
  - Per-`DamageType`: `DAMAGE_TYPE_BYTES`, `VS_DAMAGE_BYTES`. Per-`BowType`: `BOW_TYPES`. Per-`Attribute`: `ATTRIBUTE_NAMES`.
  - Stat templates: `PLUS_NUM_TEMPLATE`, `PLUS_PERCENT_TEMPLATE`, `ARMOR_BYTES`, `HEALTH_BYTES`, `ENERGY_BYTES`, `WHILE_ENCHANTED_BYTES`, `WHILE_HEALTH_BELOW_BYTES`, …
  - Number encoding: `_encode_string_table_number()` (base-`0x7F00`, mirrors the decoder), currency helpers, and composition helpers `_bonus_plus_num()`, `_dull_parenthesized()`, `_append_line_with_fallback()`, `combine_encoded_strings()`.

This builder is what the current `properties.py` / `upgrades.py` use to produce every
tooltip line. It is powerful but extremely low-level — most of `properties.py` is literally
sequences of magic bytes (see doc 03).

> **Why this matters to the redesign:** the current system chose to render tooltips by
> *re-encoding* stats into GW string bytes and decoding them back through the game table
> (so the text is authentic and localized). That's elegant in principle but is the direct
> cause of the thousands of magic-byte literals in `properties.py`/`upgrades.py`.
