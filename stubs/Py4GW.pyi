# Py4GW stub — the embedded core runtime module.
# Exact counterpart of PYBIND11_EMBEDDED_MODULE(Py4GW, m) in
# src/base/python_runtime.cpp (Py4GW_Reforged_Native).
#
# In Reforged this module is deliberately tiny: everything the legacy Py4GW
# module carried moved elsewhere — Py4GW.Console -> PySystem.Console, the
# process/game helpers -> PySystem / PyGameThread. Only version() and the
# SharedMemory submodule are registered here.


def version() -> str:
    """Runtime version string of the injected Py4GW DLL."""
    ...


class SharedMemory:
    """Shared memory publisher bindings (def_submodule)."""

    @staticmethod
    def is_ready() -> bool:
        """Whether the per-process runtime shared-memory region is mapped and valid."""
        ...

    @staticmethod
    def get_name() -> str:
        """Name of the runtime shared-memory region."""
        ...

    @staticmethod
    def get_size() -> int:
        """Byte size of the runtime shared-memory region."""
        ...

    @staticmethod
    def get_sequence() -> int:
        """Publisher sequence counter (odd = write in progress); 0 when unmapped."""
        ...
