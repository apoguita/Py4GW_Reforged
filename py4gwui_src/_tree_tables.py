import PyImGui


class _TreeTableMethods:
    """Tree, tabs, tables, and legacy columns accessors."""

    def tree_push(self, str_id: str):
        PyImGui.tree_push(str_id)

    def tree_push_ptr(self, ptr_id: int):
        PyImGui.tree_push_ptr(ptr_id)

    def tree_pop(self):
        PyImGui.tree_pop()

    def get_tree_node_to_label_spacing(self) -> float:
        return PyImGui.get_tree_node_to_label_spacing()

    def set_next_item_open(self, is_open: bool, cond: int = 0):
        PyImGui.set_next_item_open(is_open, cond)

    def set_next_item_storage_id(self, storage_id: int):
        PyImGui.set_next_item_storage_id(storage_id)

    def tree_node_get_open(self, storage_id: int) -> bool:
        return PyImGui.tree_node_get_open(storage_id)

    def collapsing_header(self, label: str, flags: int = 0) -> bool:
        return PyImGui.collapsing_header(label, flags)

    def tab_item_button(self, label: str, flags: int = 0) -> bool:
        return PyImGui.tab_item_button(label, flags)

    def set_tab_item_closed(self, label: str):
        PyImGui.set_tab_item_closed(label)

    def table_next_row(self, row_flags: int = 0, min_row_height: float = 0.0):
        PyImGui.table_next_row(row_flags, min_row_height)

    def table_next_column(self) -> bool:
        return PyImGui.table_next_column()

    def table_set_column_index(self, column_n: int) -> bool:
        return PyImGui.table_set_column_index(column_n)

    def table_setup_column(self, label: str, flags: int = 0,
                           init_width: float = 0.0, user_id: int = 0):
        PyImGui.table_setup_column(label, flags, init_width, user_id)

    def table_setup_scroll_freeze(self, cols: int, rows: int):
        PyImGui.table_setup_scroll_freeze(cols, rows)

    def table_headers_row(self):
        PyImGui.table_headers_row()

    def table_header(self, label: str):
        PyImGui.table_header(label)

    def table_angled_headers_row(self):
        PyImGui.table_angled_headers_row()

    def table_get_column_count(self) -> int:
        return PyImGui.table_get_column_count()

    def table_get_column_index(self) -> int:
        return PyImGui.table_get_column_index()

    def table_get_row_index(self) -> int:
        return PyImGui.table_get_row_index()

    def table_get_column_name(self, column_n: int = -1) -> str:
        return PyImGui.table_get_column_name(column_n)

    def table_get_column_flags(self, column_n: int = -1) -> int:
        return PyImGui.table_get_column_flags(column_n)

    def table_get_hovered_column(self) -> int:
        return PyImGui.table_get_hovered_column()

    def table_set_column_enabled(self, column_n: int, enabled: bool):
        PyImGui.table_set_column_enabled(column_n, enabled)

    def table_set_bg_color(self, target: int, color: int, column_n: int = -1):
        PyImGui.table_set_bg_color(target, color, column_n)

    def table_get_sort_specs(self):
        return PyImGui.table_get_sort_specs()

    def clear_sort_specs_dirty(self):
        PyImGui.clear_sort_specs_dirty()

    def columns(self, count: int = 1, str_id: str | None = None, borders: bool = True):
        PyImGui.columns(count, str_id, borders)

    def next_column(self):
        PyImGui.next_column()

    def end_columns(self):
        PyImGui.end_columns()

    def set_column_width(self, column_index: int, width: float):
        PyImGui.set_column_width(column_index, width)

    def set_column_offset(self, column_index: int, offset_x: float):
        PyImGui.set_column_offset(column_index, offset_x)

    def get_column_index(self) -> int:
        return PyImGui.get_column_index()

    def get_column_width(self, column_index: int = -1) -> float:
        return PyImGui.get_column_width(column_index)

    def get_column_offset(self, column_index: int = -1) -> float:
        return PyImGui.get_column_offset(column_index)

    def get_columns_count(self) -> int:
        return PyImGui.get_columns_count()
