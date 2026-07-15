"""
Merchant / Trading section — Trader, Merchant, Crafter, Collector inspection & actions.

PARITY NOTE (2026-07-12): this section is a 1:1 mirror of the legacy demo's ``ShowMerchantWindow``
(``Widgets/Coding/Py4GW_DEMO.py``). The earlier reengineered version diverged and crashed the client
on merchant access; those divergences are removed here:
  * Data path is ``GLOBAL_CACHE.Trading.*`` (throttled, cached), EXACTLY like legacy — NOT the base
    ``Py4GWCoreLib.Merchant.Trading`` wrapper (which rebuilds a ``PyMerchant()`` handle per call).
  * Only the getters legacy calls are used: ``Trader.GetOfferedItems``, ``Merchant.GetOfferedItems``,
    ``Trader.GetQuotedItemID``/``GetQuotedValue``, ``IsTransactionComplete``,
    ``Inventory.GetHoveredItemID``. The added ``GetOfferedItems2`` and ``Crafter/Collector.GetOfferedItems``
    are gone (not in legacy; the suspected fault).
  * Offered items render as RAW item ids in a 5-wide grid, like legacy — NO per-frame
    ``Item.RequestName`` name resolution (a per-frame divergence the legacy demo never does).

Actions mirror legacy exactly: Trader RequestQuote/RequestSellQuote/BuyItem/SellItem, Merchant
BuyItem/SellItem, and the Crafter/Collector trade-list (Add/Clear) + CraftItem/ExchangeItem.

NOTE: whether the merchant *actions* actually transact is a separate backend migration question —
legacy-on-Reforged reportedly has the same behaviour, so that is a wrapper/native parity issue, not
a demo-tool issue. This file only guarantees the ACCESS matches legacy so it does not crash.
"""

import PyImGui

from Py4GWCoreLib import GLOBAL_CACHE

from . import casts
from . import diagnostics
from . import ui

_SECTION = "Merchant"

_TYPES = ["Select One..", "Traders", "Merchants", "Crafters", "Collectors"]


class _State:
    type_index: int = 0
    item_id: int = 0
    cost: int = 0
    item_to_pay: int = 0
    quantity: int = 0
    hovered_item: int = 0
    trade_item_list: "list[int]" = []
    quantity_list: "list[int]" = []


state = _State()


# ---------------------------------------------------------------------------
# build_* — mirror legacy's per-frame GLOBAL_CACHE.Trading reads exactly.
# ---------------------------------------------------------------------------
def _offered_grid_block(title, ids):
    """Offered items as raw ids (legacy shows f'{item}', no name resolution)."""
    rows = [(i, item_id) for i, item_id in enumerate(ids)]
    return ui.multi_block(f"{title} ({len(rows)})", ["#", "Item ID"], rows)


def build_merchant():
    item_list = casts.safe(GLOBAL_CACHE.Trading.Trader.GetOfferedItems, default=[]) or []
    merchant_item_list = casts.safe(GLOBAL_CACHE.Trading.Merchant.GetOfferedItems, default=[]) or []
    quoted_item_id = casts.safe(GLOBAL_CACHE.Trading.Trader.GetQuotedItemID, default=0)
    quoted_value = casts.safe(GLOBAL_CACHE.Trading.Trader.GetQuotedValue, default=0)
    transaction_complete = casts.safe(GLOBAL_CACHE.Trading.IsTransactionComplete)
    hover = casts.safe(GLOBAL_CACHE.Inventory.GetHoveredItemID, default=0)
    if hover:
        state.hovered_item = hover

    status = ui.kv_block("Trader Info", [
        ("Selected Type", casts.id_name(state.type_index, _TYPES[state.type_index] if 0 <= state.type_index < len(_TYPES) else "?")),
        ("Hovered Item", state.hovered_item),
        ("Quoted Item ID", quoted_item_id),
        ("Quoted Value", quoted_value),
        ("Transaction Complete", casts.yesno(transaction_complete)),
    ])
    return [
        status,
        _offered_grid_block("Trader Offered Items", item_list),
        _offered_grid_block("Merchant/Crafter/Collector Offered Items", merchant_item_list),
    ]


# ---------------------------------------------------------------------------
# Actions — mirror legacy's GLOBAL_CACHE.Trading.* calls, fired only on click.
# ---------------------------------------------------------------------------
def _draw_actions():
    PyImGui.push_item_width(200)
    state.type_index = PyImGui.combo("Type", state.type_index, _TYPES)
    PyImGui.pop_item_width()
    state.item_id = PyImGui.input_int("Item ID", state.item_id)

    # Legacy: for Traders the cost is driven by the quoted value; otherwise user-entered.
    if state.type_index == 1:
        quoted_value = casts.safe(GLOBAL_CACHE.Trading.Trader.GetQuotedValue, default=0)
        state.cost = quoted_value
        PyImGui.text(f"Cost (from quote): {quoted_value}")
    elif state.type_index in (2, 3):
        state.cost = PyImGui.input_int("Cost", state.cost)
    else:
        state.cost = 0

    if state.type_index > 1:
        PyImGui.separator()
        PyImGui.text("Items to Pay with")
        state.item_to_pay = PyImGui.input_int("Item to Pay with", state.item_to_pay)
        state.quantity = PyImGui.input_int("Quantity", state.quantity)

    PyImGui.spacing()
    if state.type_index == 1:
        ui.section_header("Trader")
        ui.action_button("Request Trader Quote", GLOBAL_CACHE.Trading.Trader.RequestQuote, state.item_id, key="t_reqq")
        PyImGui.same_line(0, 8)
        ui.action_button("Request Trader Sell Quote", GLOBAL_CACHE.Trading.Trader.RequestSellQuote, state.item_id, key="t_reqsq")
        ui.action_button("Buy Item", GLOBAL_CACHE.Trading.Trader.BuyItem, state.item_id, state.cost, key="t_buy")
        PyImGui.same_line(0, 8)
        ui.action_button("Sell Item", GLOBAL_CACHE.Trading.Trader.SellItem, state.item_id, state.cost, key="t_sell")

    elif state.type_index == 2:
        ui.section_header("Merchant")
        ui.action_button("Buy Item", GLOBAL_CACHE.Trading.Merchant.BuyItem, state.item_id, state.cost, key="m_buy")
        PyImGui.same_line(0, 8)
        ui.action_button("Sell Item", GLOBAL_CACHE.Trading.Merchant.SellItem, state.item_id, state.cost, key="m_sell")

    if state.type_index in (3, 4):
        ui.section_header("Trade list (pay-with)")
        if PyImGui.button("Add Item"):
            state.trade_item_list.append(state.item_to_pay)
            state.quantity_list.append(state.quantity)
        PyImGui.same_line(0, 8)
        if PyImGui.button("Clear List"):
            state.trade_item_list.clear()
            state.quantity_list.clear()
        if PyImGui.begin_table("MerchantTradeList", 2, PyImGui.TableFlags.Borders):
            for idx, pay_item in enumerate(state.trade_item_list):
                PyImGui.table_next_row()
                PyImGui.table_set_column_index(0)
                PyImGui.text(f"{pay_item}")
                PyImGui.table_set_column_index(1)
                PyImGui.text(f"{state.quantity_list[idx] if idx < len(state.quantity_list) else 0}")
            PyImGui.end_table()

    if state.type_index == 3:
        ui.action_button(
            "Craft Item", GLOBAL_CACHE.Trading.Crafter.CraftItem,
            state.item_id, state.cost, state.trade_item_list, state.quantity_list, key="c_craft",
        )
    if state.type_index == 4:
        ui.action_button(
            "Exchange Item", GLOBAL_CACHE.Trading.Collector.ExchangeItem,
            state.item_id, state.cost, state.trade_item_list, state.quantity_list, key="col_x",
        )


# ---------------------------------------------------------------------------
# draw_*_view — uniform section entry point
# ---------------------------------------------------------------------------
def draw_merchant_view() -> None:
    blocks = build_merchant()
    diagnostics.dump_button(_SECTION, blocks)
    PyImGui.separator()
    if PyImGui.begin_tab_bar("MerchantTabs"):
        if PyImGui.begin_tab_item("Data"):
            ui.draw_blocks(_SECTION, blocks)
            PyImGui.end_tab_item()
        if PyImGui.begin_tab_item("Actions"):
            _draw_actions()
            PyImGui.end_tab_item()
        PyImGui.end_tab_bar()
