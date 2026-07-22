# PyTexture stub — Reforged Native surface
# Matches src/GW/textures/texture_bindings.cpp.
# Every getter returns an ImGui texture handle (the D3D9 texture pointer as an
# int, 0 when not ready), usable directly with PyImGui.image().

def get_file_texture(path: str) -> int:
    """Load a texture from a file path (PNG/JPG/BMP/... via WIC). Cached."""
    ...

def get_dat_texture(key: str) -> int:
    """Load a texture by cache key. 'gwdat://<file_id>' routes to the GW.dat reader."""
    ...

def get_texture_by_file_id(file_id: int) -> int:
    """Load a texture directly from the GW.dat archive by file id. Decodes
    asynchronously; returns 0 until the upload completes (call again next frame)."""
    ...

def get_colored_model_texture(
    model_file_id: int,
    dye_tint: int = 0,
    dye1: int = 0,
    dye2: int = 0,
    dye3: int = 0,
    dye4: int = 0,
) -> int:
    """Load a dyed/colored model texture from the GW.dat archive (base icon + dye
    mask blended with the client dye colors). Async, like get_texture_by_file_id."""
    ...

def cleanup_old_textures(timeout_seconds: int = 30) -> None:
    """Release textures unused for longer than timeout_seconds."""
    ...
