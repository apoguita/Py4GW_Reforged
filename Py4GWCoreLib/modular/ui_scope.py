"""Exception-safe structural scopes for modular PyImGui surfaces."""

from __future__ import annotations

from contextlib import contextmanager
from functools import wraps
from typing import Any
from typing import Callable
from typing import Iterator
from typing import Sequence

import PyImGui


@contextmanager
def window_scope(name: str, flags: int = 0) -> Iterator[bool]:
    entered = False
    try:
        visible = bool(PyImGui.begin(name, flags))
        entered = True
        yield visible
    finally:
        if entered:
            PyImGui.end()


def window_frame(name: str, flags: int = 0) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorate a per-frame draw function with one exception-safe ImGui window."""

    def decorate(draw_fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(draw_fn)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            with window_scope(name, flags) as visible:
                if not visible:
                    return None
                return draw_fn(*args, **kwargs)

        return wrapped

    return decorate


@contextmanager
def tooltip_scope() -> Iterator[None]:
    PyImGui.begin_tooltip()
    try:
        yield
    finally:
        PyImGui.end_tooltip()


@contextmanager
def child_scope(
    identifier: str,
    size: Sequence[float] = (0.0, 0.0),
    border: int = 0,
    flags: int = 0,
) -> Iterator[bool]:
    entered = False
    try:
        visible = bool(PyImGui.begin_child(identifier, size, border, flags))
        entered = True
        yield visible
    finally:
        if entered:
            PyImGui.end_child()


@contextmanager
def table_scope(
    identifier: str,
    columns: int,
    flags: int = 0,
    outer_size: Sequence[float] = (0.0, 0.0),
    inner_width: float = 0.0,
) -> Iterator[bool]:
    entered = False
    try:
        visible = bool(PyImGui.begin_table(identifier, columns, flags, outer_size, inner_width))
        entered = True
        yield visible
    finally:
        if entered:
            PyImGui.end_table()


@contextmanager
def tab_bar_scope(identifier: str, flags: int = 0) -> Iterator[bool]:
    entered = False
    try:
        visible = bool(PyImGui.begin_tab_bar(identifier, flags))
        entered = True
        yield visible
    finally:
        if entered:
            PyImGui.end_tab_bar()


@contextmanager
def tab_item_scope(label: str) -> Iterator[bool]:
    opened = bool(PyImGui.begin_tab_item(label))
    try:
        yield opened
    finally:
        if opened:
            PyImGui.end_tab_item()


@contextmanager
def disabled_scope(disabled: bool) -> Iterator[None]:
    PyImGui.begin_disabled(bool(disabled))
    try:
        yield
    finally:
        PyImGui.end_disabled()


@contextmanager
def group_scope() -> Iterator[None]:
    PyImGui.begin_group()
    try:
        yield
    finally:
        PyImGui.end_group()


@contextmanager
def style_colors_scope(count: int) -> Iterator[None]:
    try:
        yield
    finally:
        if count > 0:
            PyImGui.pop_style_color(int(count))
