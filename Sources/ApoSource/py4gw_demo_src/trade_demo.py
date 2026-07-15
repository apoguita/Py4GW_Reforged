"""
Trade section — native ``PyTrade`` (R2 module #30, batch b3).

Shape mirrors ``player_demo.py`` (the canonical template):
  * ``build_trade()`` casts every readable value via ``casts`` and returns display Blocks.
  * ``draw_trade_view()`` renders those blocks, exposes every mutator/query binding as an
    explicit trigger button (never auto-fired), and offers the per-section Dump button.

IMPORTANT — the stub ``PyTrading.pyi`` is FICTIONAL (declares a PascalCase class ``PyTrading``
with methods that are NOT bound). The live module is ``PyTrade``: eight snake_case FREE
functions. We wire the native surface directly, ignoring the stub.

PyTrade is almost entirely an ACTION surface — none of the eight functions is a no-arg state
getter (the stub's ``IsTradeInitiated`` / ``IsTradeAccepted`` / ``IsTradeOffered`` are not
bound). The only readable is ``is_item_offered(item_id)``, a subject-id query; it is surfaced
both as a live Data row (driven by the query input) and as an explicit Actions button.

R2 coverage (PyTrade, 8/8 wired, 0 skipped):
  Actions wired: open_trade_window, accept_trade, cancel_trade, change_offer, submit_offer,
    remove_item, offer_item.
  Query wired (Data + Actions): is_item_offered.
"""

import PyImGui

import PyTrade

from . import casts
from . import diagnostics
from . import ui

_SECTION = "Trade"


class _State:
    open_agent_id: int = 0
    submit_gold: int = 0
    remove_slot: int = 0
    offer_item_id: int = 0
    offer_quantity: int = 0
    query_item_id: int = 0


state = _State()


# ---------------------------------------------------------------------------
# build_* — read the (single) query getter, cast, return blocks
# ---------------------------------------------------------------------------
def _module_block():
    rows = [
        ("Module", "PyTrade (native, snake_case free functions)"),
        ("Bound functions", 8),
        ("No-arg state getters", "None bound (stub IsTradeInitiated/etc. are fictional)"),
        ("Readable query", "is_item_offered(item_id)"),
    ]
    return ui.kv_block("Module", rows)


def _query_block():
    offered = casts.safe(PyTrade.is_item_offered, int(state.query_item_id))
    rows = [
        ("Query Item ID", state.query_item_id),
        ("Is Item Offered", casts.yesno(offered) if offered is not None else "<n/a>"),
    ]
    return ui.kv_block("Item Offered Query (set item id in Actions)", rows)


def build_trade():
    return [_module_block(), _query_block()]


# ---------------------------------------------------------------------------
# Actions — explicit trigger buttons, fired only on click
# ---------------------------------------------------------------------------
def _draw_actions():
    ui.section_header("Trade Window")
    state.open_agent_id = PyImGui.input_int("Partner Agent ID", state.open_agent_id)
    ui.action_button("Open Trade Window", PyTrade.open_trade_window, state.open_agent_id, key="open_trade")
    PyImGui.same_line(0, 8)
    ui.action_button("Accept Trade", PyTrade.accept_trade, key="accept_trade")
    PyImGui.same_line(0, 8)
    ui.action_button("Cancel Trade", PyTrade.cancel_trade, key="cancel_trade")

    PyImGui.spacing()
    ui.section_header("Offer")
    ui.action_button("Change Offer", PyTrade.change_offer, key="change_offer")
    state.submit_gold = PyImGui.input_int("Submit Gold", state.submit_gold)
    ui.action_button("Submit Offer", PyTrade.submit_offer, state.submit_gold, key="submit_offer")

    PyImGui.spacing()
    ui.section_header("Items")
    state.offer_item_id = PyImGui.input_int("Offer Item ID", state.offer_item_id)
    state.offer_quantity = PyImGui.input_int("Offer Quantity", state.offer_quantity)
    ui.action_button("Offer Item", PyTrade.offer_item, state.offer_item_id, state.offer_quantity, key="offer_item")
    state.remove_slot = PyImGui.input_int("Remove Slot / Item ID", state.remove_slot)
    ui.action_button("Remove Item", PyTrade.remove_item, state.remove_slot, key="remove_item")

    PyImGui.spacing()
    ui.section_header("Query")
    state.query_item_id = PyImGui.input_int("Query Item ID", state.query_item_id)
    ui.action_button("Is Item Offered", PyTrade.is_item_offered, state.query_item_id, key="is_item_offered")


# ---------------------------------------------------------------------------
# draw_*_view — uniform section entry point
# ---------------------------------------------------------------------------
def draw_trade_view() -> None:
    blocks = build_trade()
    diagnostics.dump_button(_SECTION, blocks)
    PyImGui.separator()
    if PyImGui.begin_tab_bar("TradeTabs"):
        if PyImGui.begin_tab_item("Data"):
            ui.draw_blocks(_SECTION, blocks)
            PyImGui.end_tab_item()
        if PyImGui.begin_tab_item("Actions"):
            _draw_actions()
            PyImGui.end_tab_item()
        PyImGui.end_tab_bar()
