"""Seletores nativos sem dependencias opcionais como tkinter."""

import os
import sys


class NativeDialogError(RuntimeError):
    pass


def _windows_folder_dialog(title: str) -> str | None:
    import ctypes
    from ctypes import wintypes

    class BROWSEINFOW(ctypes.Structure):
        _fields_ = [
            ("hwndOwner", wintypes.HWND), ("pidlRoot", ctypes.c_void_p),
            ("pszDisplayName", wintypes.LPWSTR), ("lpszTitle", wintypes.LPCWSTR),
            ("ulFlags", wintypes.UINT), ("lpfn", ctypes.c_void_p),
            ("lParam", wintypes.LPARAM), ("iImage", ctypes.c_int),
        ]

    ole32, shell32 = ctypes.windll.ole32, ctypes.windll.shell32
    user32 = ctypes.windll.user32
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    shell32.SHGetPathFromIDListW.argtypes = [ctypes.c_void_p, wintypes.LPWSTR]
    shell32.SHGetPathFromIDListW.restype = wintypes.BOOL
    ole32.CoInitializeEx(None, 0x2)
    try:
        display_name = ctypes.create_unicode_buffer(32768)
        info = BROWSEINFOW()
        owner = user32.GetForegroundWindow()
        info.hwndOwner = owner
        info.pszDisplayName = ctypes.cast(display_name, wintypes.LPWSTR)
        info.lpszTitle = title
        info.ulFlags = 0x0001 | 0x0010 | 0x0040
        shell32.SHBrowseForFolderW.restype = ctypes.c_void_p
        if owner:
            user32.SetForegroundWindow(owner)
        pidl = shell32.SHBrowseForFolderW(ctypes.byref(info))
        if not pidl:
            return None
        try:
            selected = ctypes.create_unicode_buffer(32768)
            if not shell32.SHGetPathFromIDListW(pidl, selected):
                raise NativeDialogError("O Windows não retornou uma pasta válida.")
            return os.path.normpath(selected.value)
        finally:
            ole32.CoTaskMemFree(pidl)
    finally:
        ole32.CoUninitialize()


def _windows_file_dialog(title: str) -> str | None:
    import ctypes
    from ctypes import wintypes

    class OPENFILENAMEW(ctypes.Structure):
        _fields_ = [
            ("lStructSize", wintypes.DWORD), ("hwndOwner", wintypes.HWND),
            ("hInstance", wintypes.HINSTANCE), ("lpstrFilter", wintypes.LPCWSTR),
            ("lpstrCustomFilter", wintypes.LPWSTR), ("nMaxCustFilter", wintypes.DWORD),
            ("nFilterIndex", wintypes.DWORD), ("lpstrFile", wintypes.LPWSTR),
            ("nMaxFile", wintypes.DWORD), ("lpstrFileTitle", wintypes.LPWSTR),
            ("nMaxFileTitle", wintypes.DWORD), ("lpstrInitialDir", wintypes.LPCWSTR),
            ("lpstrTitle", wintypes.LPCWSTR), ("Flags", wintypes.DWORD),
            ("nFileOffset", wintypes.WORD), ("nFileExtension", wintypes.WORD),
            ("lpstrDefExt", wintypes.LPCWSTR), ("lCustData", wintypes.LPARAM),
            ("lpfnHook", ctypes.c_void_p), ("lpTemplateName", wintypes.LPCWSTR),
            ("pvReserved", ctypes.c_void_p), ("dwReserved", wintypes.DWORD),
            ("FlagsEx", wintypes.DWORD),
        ]

    ole32 = ctypes.windll.ole32
    ole32.CoInitializeEx(None, 0x2)
    try:
        selected = ctypes.create_unicode_buffer(32768)
        dialog = OPENFILENAMEW()
        dialog.lStructSize = ctypes.sizeof(OPENFILENAMEW)
        user32 = ctypes.windll.user32
        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        owner = user32.GetForegroundWindow()
        dialog.hwndOwner = owner
        dialog.lpstrFilter = (
            "Bases de dados (*.xlsx;*.xlsm;*.xlsb;*.xls;*.csv;*.parquet)\0"
            "*.xlsx;*.xlsm;*.xlsb;*.xls;*.csv;*.parquet\0"
            "Todos os arquivos (*.*)\0*.*\0\0"
        )
        dialog.lpstrFile = ctypes.cast(selected, wintypes.LPWSTR)
        dialog.nMaxFile = len(selected)
        dialog.lpstrTitle = title
        dialog.Flags = 0x00001000 | 0x00000800 | 0x00080000 | 0x00000008
        if owner:
            user32.SetForegroundWindow(owner)
        if not ctypes.windll.comdlg32.GetOpenFileNameW(ctypes.byref(dialog)):
            error = ctypes.windll.comdlg32.CommDlgExtendedError()
            if error:
                raise NativeDialogError(f"Falha do seletor do Windows (código {error}).")
            return None
        return os.path.normpath(selected.value)
    finally:
        ole32.CoUninitialize()


def select_path(mode: str) -> str | None:
    if mode not in {"folder", "file"}:
        raise ValueError("Modo de seleção inválido.")
    if sys.platform == "win32":
        return (_windows_folder_dialog("Selecionar pasta de dados") if mode == "folder"
                else _windows_file_dialog("Selecionar arquivo de dados"))
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError as exc:
        raise NativeDialogError("Digite ou cole o caminho: seletor gráfico indisponível neste sistema.") from exc
    root = tk.Tk()
    try:
        root.withdraw(); root.attributes("-topmost", True)
        if mode == "folder":
            return filedialog.askdirectory(title="Selecionar pasta de dados") or None
        return filedialog.askopenfilename(title="Selecionar arquivo de dados") or None
    finally:
        root.destroy()
