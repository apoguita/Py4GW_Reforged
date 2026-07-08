import PyImGui


class _DockingMethods:
    def dock_space(self, dock_id: int, size=(0, 0), flags: int = 0) -> int:
        return PyImGui.dock_space(dock_id, size, flags)
    def dock_space_over_viewport(self, dockspace_id: int = 0, flags: int = 0) -> int:
        return PyImGui.dock_space_over_viewport(dockspace_id, flags)
    def set_next_window_dock_id(self, dock_id: int, cond: int = 0):
        PyImGui.set_next_window_dock_id(dock_id, cond)
    def get_window_dock_id(self) -> int:
        return PyImGui.get_window_dock_id()
    def is_window_docked(self) -> bool:
        return PyImGui.is_window_docked()
    def dock_builder_dock_window(self, window_name: str, node_id: int):
        PyImGui.dock_builder_dock_window(window_name, node_id)
    def dock_builder_add_node(self, node_id: int = 0, flags: int = 0) -> int:
        return PyImGui.dock_builder_add_node(node_id, flags)
    def dock_builder_remove_node(self, node_id: int):
        PyImGui.dock_builder_remove_node(node_id)
    def dock_builder_remove_node_child_nodes(self, node_id: int):
        PyImGui.dock_builder_remove_node_child_nodes(node_id)
    def dock_builder_remove_node_docked_windows(self, node_id: int,
                                                  clear_settings: bool = True):
        PyImGui.dock_builder_remove_node_docked_windows(node_id, clear_settings)
    def dock_builder_set_node_pos(self, node_id: int, pos):
        PyImGui.dock_builder_set_node_pos(node_id, pos)
    def dock_builder_set_node_size(self, node_id: int, size):
        PyImGui.dock_builder_set_node_size(node_id, size)
    def dock_builder_split_node(self, node_id: int, split_dir: int,
                                 size_ratio: float):
        return PyImGui.dock_builder_split_node(node_id, split_dir, size_ratio)
    def dock_builder_finish(self, node_id: int):
        PyImGui.dock_builder_finish(node_id)
