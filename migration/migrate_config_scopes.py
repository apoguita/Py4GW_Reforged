"""One-time config-scope migration.

Some configs changed their native ``Settings`` scope:

- Widget manager (both versions: ``Py4GW_widget_manager`` + ``Py4GW_widget_catalog``)
  moved **global -> account**.
- Inventory+ moved **account -> global**.

Native Settings stores each scope in a different file on disk
(``settings/Global/<name>`` vs ``settings/<email>/<name>``), so flipping the scope in
code alone would strand the existing data in the old file. This script copies the
existing values from the OLD scope into the NEW scope so nothing is lost.

Idempotent + non-clobbering: a key already present in the destination is left untouched,
so re-running is safe and never overwrites values the user changed after migrating.

Run it **in-client, after logging in** (native ``PySettings`` must be loaded, and the
account anchor/email must be resolved for account scope). Two ways to run:
  * call ``run_migration()`` directly (e.g. from the console/bridge), or
  * drop a ``.widget`` marker in this folder so the widget manager loads it - ``main()``
    self-runs the migration once and then idles.
"""

from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings

MODULE_NAME = "ConfigScopeMigration"

# (document name, from_scope, to_scope)
MIGRATIONS = [
    # Widget manager: global -> account
    ("Widgets/WidgetManager/WidgetManager.ini", "global", "account"),
    ("Widgets/WidgetCatalog/WidgetCatalog.ini", "global", "account"),
    ("Widgets/WidgetCatalog/WidgetCatalogFloatingButton.ini", "global", "account"),
    ("Widgets/WidgetCatalog/WidgetCatalogSetup.ini", "global", "account"),
    # Inventory+: account -> global
    ("Widgets/Config/InventoryPlus.ini", "account", "global"),
    ("Inventory/InventoryPlus/InventoryPlus.ini", "account", "global"),
]


def _log(message, error=False):
    try:
        import PySystem
        level = PySystem.Console.MessageType.Error if error else PySystem.Console.MessageType.Info
        PySystem.Console.Log(MODULE_NAME, message, level)
    except Exception:
        pass


def migrate_document(name, from_scope, to_scope):
    """Copy every (section, key) from the from_scope doc into the to_scope doc without
    clobbering keys the destination already has. Returns the number of keys copied."""
    src = Settings(name, from_scope)
    dst = Settings(name, to_scope)
    copied = 0
    for section in src.sections():
        for key, value in src.items(section).items():
            if not dst.has(section, key):
                dst.set(section, key, value)
                copied += 1
    if copied:
        dst.save()
    return copied


def run_migration():
    """Run every scope migration. Returns the total number of keys copied."""
    total = 0
    for name, from_scope, to_scope in MIGRATIONS:
        try:
            count = migrate_document(name, from_scope, to_scope)
            total += count
            _log(f"{name}: {from_scope} -> {to_scope} ({count} keys copied)")
        except Exception as exc:
            _log(f"{name}: migration failed: {exc}", error=True)
    _log(f"Config scope migration complete ({total} keys copied).")
    return total


# --- Optional widget entry point (only used if a .widget marker is added here) ---
_has_run = False


def main():
    global _has_run
    if _has_run:
        return
    _has_run = True
    run_migration()
