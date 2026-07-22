# PyScanner.pyi
#
# Exact counterpart of src/base/scanner_bindings.cpp.
# Every member is a def_static on the PyScanner class; the class itself has no
# py::init and cannot be instantiated from Python.
#
# `section` is a raw uint8 index matching PY4GW::ScannerSection
# (0 = .text, 1 = .rdata, 2 = .data).
#
# Methods bound WITHOUT py::arg() take positional-only arguments (marked with
# `/`) and expose no C++ default values — every parameter must be supplied.

from typing import Any, Dict, Tuple


class PyScanner:
    # ------------------------------
    # Initialization
    # ------------------------------
    @staticmethod
    def Initialize(module_name: str = "") -> None:
        """
        Initialize the scanner for the given module.
        If module_name is empty, the main module is scanned.
        """

    # ------------------------------
    # Pattern scanning
    # ------------------------------
    @staticmethod
    def Find(pattern: bytes, mask: str, offset: int, section: int, /) -> int:
        """
        Scan for a byte pattern inside a memory section.
        Returns the found address or 0.
        """

    @staticmethod
    def FindInRange(pattern: bytes, mask: str, offset: int,
                    start: int, end: int, /) -> int:
        """
        Scan for a byte pattern within an explicit address range.
        Returns the found address or 0.
        """

    @staticmethod
    def FindAssertion(assertion_file: str,
                      assertion_msg: str,
                      line_number: int = 0,
                      offset: int = 0) -> int:
        """
        Find an assertion in the binary by its file name and message.
        Optionally specify line number and offset.
        Returns the found address or 0.
        """

    @staticmethod
    def GetSectionAddressRange(section: int) -> Tuple[int, int]:
        """
        Get the start and end addresses of a memory section.
        Always returns a (start, end) tuple; an invalid section yields (0, 0).
        """

    # ------------------------------
    # Function resolution helpers
    # ------------------------------
    @staticmethod
    def FunctionFromNearCall(call_instruction_address: int,
                             check_valid_ptr: bool, /) -> int:
        """
        Given an address of a near CALL/JMP instruction,
        resolve the absolute target function address.
        """

    @staticmethod
    def ToFunctionStart(address: int, scan_range: int, /) -> int:
        """
        Scan backwards from 'address' to find a function prologue.
        Typically returns a function start or 0.
        The legacy default scan_range was 0xFF; it is NOT bound, pass it explicitly.
        """

    # ------------------------------
    # Pointer validation
    # ------------------------------
    @staticmethod
    def IsValidPtr(address: int, section: int, /) -> bool:
        """
        Check whether 'address' is inside the memory range
        of the specified section (.text, .rdata, .data).
        """

    # ------------------------------
    # Address usage scanning
    # ------------------------------
    @staticmethod
    def FindUseOfAddress(address: int, offset: int, section: int, /) -> int:
        """
        Find the first occurrence of a raw address inside instructions.
        Returns the location or 0.
        """

    @staticmethod
    def FindNthUseOfAddress(address: int, nth: int,
                            offset: int, section: int, /) -> int:
        """
        Find the nth occurrence of a raw address inside instructions.
        Returns the location or 0.
        """

    # ------------------------------
    # String usage scanning — ANSI
    # ------------------------------
    @staticmethod
    def FindUseOfStringA(string: str, offset: int, section: int, /) -> int:
        """
        Find the first code reference to an ANSI string.
        """

    @staticmethod
    def FindNthUseOfStringA(string: str, nth: int,
                            offset: int, section: int, /) -> int:
        """
        Find the nth reference to an ANSI string.
        """

    # ------------------------------
    # String usage scanning — WIDE
    # ------------------------------
    @staticmethod
    def FindUseOfStringW(string: str, offset: int, section: int, /) -> int:
        """
        Find the first code reference to a wide-character string.
        """

    @staticmethod
    def FindNthUseOfStringW(string: str, nth: int,
                            offset: int, section: int, /) -> int:
        """
        Find the nth reference to a wide-character string.
        """

    # ------------------------------
    # Diagnostics
    # ------------------------------
    @staticmethod
    def GetScanStatus() -> Dict[str, Dict[str, Any]]:
        """
        Recorded pattern-scan and hook results.

        Returns a dict with two entries:
          "scans" -> {name: resolved_address}
          "hooks" -> {name: MH_STATUS}  (0 == MH_OK)
        """
