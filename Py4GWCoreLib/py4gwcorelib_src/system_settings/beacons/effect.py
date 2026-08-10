"""Drawing a beacon. The geometry is the reference's, made **poolable**.

`light_beacon.py` draws exactly one beacon at the player. A marking feature draws one per matched
drop, so the only real change here is lifetime management:

* **Emitter handles are pooled.** A C++ emitter is a real allocation and dropping the handle frees the
  effect, so handles are lent to a beacon while it is on screen and returned when it stops being
  shown -- rather than created and destroyed as drops come and go.
* **The ground profile cache is a dict, not one slot.** The reference caches a single profile, which
  is right for one beacon and useless for twenty: every beacon would evict the previous one's entry
  and re-sample every frame. Keyed by cell, each beacon keeps its own. This is a consequence of
  pooling, not a change of behaviour.

Usage is per frame::

    beacons.show(key, x, y, preset)   # once per visible beacon
    beacons.end_frame()               # releases every beacon not shown this frame

Nothing here decides *what* to draw a beacon on. That is the marking feature's job.
"""

import math

_TAU = math.pi * 2.0

#: Points sampled around a beacon to capture the terrain slope. One batched call per beacon.
GROUND_SAMPLES = 36
#: Cached ground profiles. Bounded so a long session cannot grow it without limit.
_MAX_PROFILES = 256


def _argb(rgba, alpha_factor: float = 1.0) -> int:
    r = max(0, min(255, int(rgba[0] * 255)))
    g = max(0, min(255, int(rgba[1] * 255)))
    b = max(0, min(255, int(rgba[2] * 255)))
    a = max(0, min(255, int(rgba[3] * 255 * alpha_factor)))
    return (a << 24) | (r << 16) | (g << 8) | b


# ---------------------------------------------------------------- geometry (from the reference)


def _beam_quads(x, y, gz, height, base_w, top_w, base_rgba, mid_rgba, top_rgba,
                alpha_mul, num_quads, mid_frac):
    """N crossed vertical quads, evenly rotated about the vertical axis (2 = an X, 3 = a
    6-pointed star seen from above). Each quad has a 3-stop vertical gradient; the GPU
    interpolates between the stops."""
    half_base, half_top = base_w * 0.5, top_w * 0.5
    half_mid = half_base + (half_top - half_base) * mid_frac
    levels = (
        (0.0, half_base, _argb(base_rgba, base_rgba[3] * alpha_mul)),
        (mid_frac, half_mid, _argb(mid_rgba, mid_rgba[3] * alpha_mul)),
        (1.0, half_top, _argb(top_rgba, top_rgba[3] * alpha_mul)),
    )
    verts = []
    count = max(1, int(num_quads))
    for i in range(count):
        theta = i * math.pi / count          # planes spread over 180 degrees
        ax, ay = math.cos(theta), math.sin(theta)
        rows = [((x - ax * half, y - ay * half, gz - height * f, col),
                 (x + ax * half, y + ay * half, gz - height * f, col))
                for f, half, col in levels]
        for r in range(len(rows) - 1):
            (l0, r0), (l1, r1) = rows[r], rows[r + 1]
            verts.extend([l0, r0, r1, l0, r1, l1])
    return verts


def _cone(x, y, gz, height, base_r, top_r, rgbas, alpha_mul, mid_frac, segments):
    """Open frustum tube about the vertical axis with a 3-stop vertical gradient. The strong core is
    drawn with this, then a wider copy supplies the glow halo."""
    base_c = _argb(rgbas[0], rgbas[0][3] * alpha_mul)
    mid_c = _argb(rgbas[1], rgbas[1][3] * alpha_mul)
    top_c = _argb(rgbas[2], rgbas[2][3] * alpha_mul)
    mid_r = base_r + (top_r - base_r) * mid_frac
    levels = ((0.0, base_r, base_c), (mid_frac, mid_r, mid_c), (1.0, top_r, top_c))
    seg = max(3, int(segments))
    ring = [(math.cos(k / seg * _TAU), math.sin(k / seg * _TAU)) for k in range(seg + 1)]
    verts = []
    for index in range(len(levels) - 1):
        f0, r0, c0 = levels[index]
        f1, r1, c1 = levels[index + 1]
        z0, z1 = gz - height * f0, gz - height * f1
        for k in range(seg):
            cx0, cy0 = ring[k]
            cx1, cy1 = ring[k + 1]
            b0 = (x + cx0 * r0, y + cy0 * r0, z0, c0)
            b1 = (x + cx1 * r0, y + cy1 * r0, z0, c0)
            t0 = (x + cx0 * r1, y + cy0 * r1, z1, c1)
            t1 = (x + cx1 * r1, y + cy1 * r1, z1, c1)
            verts.extend([b0, b1, t1, b0, t1, t0])
    return verts


def _prof_z(profile, angle: float) -> float:
    """Ground Z from a profile at the nearest sampled angle."""
    return profile[int(round(angle / _TAU * len(profile))) % len(profile)]


def _base_disc(x, y, cz, profile, radius, rgba, alpha_mul, segments: int = 36):
    """Glow disc; the rim follows the terrain via the shared angular profile."""
    center_c = _argb(rgba, rgba[3] * 0.8 * alpha_mul)
    edge_c = _argb(rgba, 0.0)
    center = (x, y, cz, center_c)
    rim = []
    for i in range(segments + 1):
        angle = i / segments * _TAU
        rim.append((x + math.cos(angle) * radius, y + math.sin(angle) * radius,
                    _prof_z(profile, angle), edge_c))
    verts = []
    for i in range(segments):
        verts.extend([center, rim[i], rim[i + 1]])
    return verts


def _ring(x, y, profile, radius, thickness, rgba, alpha, segments: int = 44):
    """Soft annulus following the terrain via the shared angular profile."""
    mid_c = _argb(rgba, rgba[3] * alpha)
    edge_c = _argb(rgba, 0.0)
    r_in, r_out = max(0.0, radius - thickness), radius + thickness
    inner, mid, outer = [], [], []
    for i in range(segments + 1):
        angle = (i / segments) * _TAU
        ca, sa = math.cos(angle), math.sin(angle)
        z = _prof_z(profile, angle)
        inner.append((x + ca * r_in, y + sa * r_in, z, edge_c))
        mid.append((x + ca * radius, y + sa * radius, z, mid_c))
        outer.append((x + ca * r_out, y + sa * r_out, z, edge_c))
    verts = []
    for i in range(segments):
        verts.extend([inner[i], mid[i], mid[i + 1], inner[i], mid[i + 1], inner[i + 1]])
        verts.extend([mid[i], outer[i], outer[i + 1], mid[i], outer[i + 1], mid[i + 1]])
    return verts


# ---------------------------------------------------------------- the pooled renderer


class BeaconRenderer:
    """Draws any number of beacons, lending pooled emitter handles to each while it is visible."""

    def __init__(self) -> None:
        self._dx = None
        self._overlay = None
        #: key -> borrowed emitter handles, for beacons currently on screen.
        self._lent: dict = {}
        #: handles nobody is using, kept rather than freed so a reappearing drop costs nothing.
        self._free: list = []
        self._seen: set = set()
        self._profiles: dict = {}
        self._frame = 0
        self.frozen = False
        self.status = "idle"

    # -- native handles, resolved lazily so this module stays import-safe offline --

    def _renderer(self):
        if self._dx is None:
            import PyDXOverlay

            self._dx = PyDXOverlay.get_overlay()
        return self._dx

    def _ov(self):
        if self._overlay is None:
            import PyOverlay

            self._overlay = PyOverlay.Overlay()
        return self._overlay

    def _ground_z(self, x: float, y: float) -> float:
        # FindZ resolves the topmost surface across all planes, so a fixed point stays on its
        # slope or bridge regardless of the player's plane.
        try:
            return self._ov().FindZ(x, y)
        except Exception:
            return 0.0

    def _ground_profile(self, x: float, y: float, radius: float, lift: float):
        """The terrain ring around one beacon: one batched sample, cached per ~8-unit cell.

        A dict rather than the reference's single slot -- with several beacons alive, one slot is
        evicted by whichever drew last and nothing is ever cached.
        """
        key = (round(x / 8.0), round(y / 8.0), round(radius), round(lift))
        cached = self._profiles.get(key)
        if cached is not None:
            return cached
        points = [(x + math.cos(i / GROUND_SAMPLES * _TAU) * radius,
                   y + math.sin(i / GROUND_SAMPLES * _TAU) * radius) for i in range(GROUND_SAMPLES)]
        try:
            zs = self._ov().FindZBatch(points, True)
        except Exception:
            zs = [self._ground_z(px, py) for px, py in points]
        profile = [z - lift for z in zs]
        if len(self._profiles) >= _MAX_PROFILES:
            self._profiles.clear()
        self._profiles[key] = profile
        return profile

    def invalidate_ground(self) -> None:
        """The terrain is not the same terrain any more -- called on a map change."""
        self._profiles.clear()

    # -- emitter pool --

    def _take(self, count: int) -> list:
        try:
            import PyParticles
        except Exception:
            return []
        out = []
        for _ in range(count):
            if self._free:
                out.append(self._free.pop())
            else:
                try:
                    out.append(PyParticles.create_emitter())
                except Exception:
                    break
        return out

    def _give_back(self, handles) -> None:
        for handle in handles:
            try:
                handle.config.enabled = False
                handle.clear()
            except Exception:
                continue
            self._free.append(handle)

    def _apply_emitter(self, handle, emitter) -> None:
        from .model import EMITTER_KEYS

        config = handle.config
        for key in EMITTER_KEYS:
            setattr(config, key, float(emitter.params[key]))
        config.mode = int(emitter.mode)
        config.additive = bool(emitter.additive)
        # Mute is honoured here, so what is drawn agrees with the cost figure the editor shows.
        config.enabled = bool(emitter.enabled) and not bool(emitter.muted)
        packed = _argb(emitter.color)
        config.color = packed
        config.color_end = packed & 0x00FFFFFF   # fade to transparent, same rgb

    # -- drawing --

    def _draw_beam(self, verts, blend: int) -> None:
        """2 = MAX (bright and coloured; it cannot exceed the source colour, so it never washes to
        white), 1 = additive, 0 = alpha. MAX needs ``draw_shaded_3d_max``; falls back to alpha."""
        renderer = self._renderer()
        if blend == 2:
            try:
                renderer.draw_shaded_3d_max(verts, True)
                return
            except AttributeError:
                pass
        renderer.draw_shaded_3d(verts, blend == 1, True)

    def show(self, key, x: float, y: float, preset, alpha: float = 1.0) -> None:
        """Draw one beacon this frame. Call again next frame to keep it alive."""
        try:
            self._show(key, float(x), float(y), preset, float(alpha))
        except AttributeError as exc:
            self.status = "missing binding (rebuild the DLL): %s" % exc
        except Exception as exc:
            self.status = "error: %s" % exc

    def _show(self, key, x: float, y: float, preset, alpha: float) -> None:
        self._seen.add(key)
        params, colors = preset.params, preset.colors
        phase = self._frame * 0.07
        pulse = bool(params.get("pulse", False))
        beam_a = alpha * ((0.88 + 0.12 * math.sin(phase * 2.0)) if pulse else 1.0)
        disc_a = alpha * ((0.85 + 0.15 * math.sin(phase * 1.3)) if pulse else 1.0)
        gz = self._ground_z(x, y)
        ground_additive = bool(params.get("ground_additive", False))
        stops = (colors["beam_base"], colors["beam_mid"], colors["beam_top"])

        # All beam geometry goes into ONE vertex list -> one draw call. Triangles render in buffer
        # order, so appending shells widest-first and the core last keeps the layering exact.
        verts = []
        if int(params.get("beam_shape", 1)) == 1:
            base_r, top_r = params["base_w"] * 0.5, params["top_w"] * 0.5
            segments, mid_frac = int(params["beam_segments"]), params["beam_mid_frac"]
            glow = float(params.get("beam_glow", 0.0))
            if glow > 0.001:
                scale = float(params["beam_glow_scale"])
                shells = max(1, int(params["beam_glow_shells"]))
                for shell in range(shells, 0, -1):
                    t = shell / shells                       # 1 = outer edge .. inner
                    radius_scale = 1.0 + (scale - 1.0) * t
                    shell_a = glow * (1.0 - t) * (1.0 - t)   # 0 at the outer edge, grows inward
                    verts += _cone(x, y, gz, params["height"], base_r * radius_scale,
                                   top_r * radius_scale, stops, beam_a * shell_a, mid_frac, segments)
            verts += _cone(x, y, gz, params["height"], base_r, top_r, stops, beam_a, mid_frac,
                           segments)
        else:
            verts = _beam_quads(x, y, gz, params["height"], params["base_w"], params["top_w"],
                                colors["beam_base"], colors["beam_mid"], colors["beam_top"],
                                beam_a, int(params.get("beam_quads", 2)), params["beam_mid_frac"])
        self._draw_beam(verts, int(params.get("beam_blend", 2)))

        # Ground: one angular profile shared by the disc and every ring, so conforming to the
        # terrain costs the same whatever the ring count.
        lift = float(params.get("ground_lift", 0.0))
        radius = float(params["disc_radius"])
        profile = self._ground_profile(x, y, radius, lift)
        renderer = self._renderer()
        renderer.draw_shaded_3d(_base_disc(x, y, gz - lift, profile, radius, colors["disc"], disc_a),
                                ground_additive, True)

        rings = max(0, int(params.get("rings", 0)))
        for k in range(rings):
            ring_phase = (self._frame * 0.012 * float(params["ring_speed"]) + k / max(1, rings)) % 1.0
            ring_r = radius * (0.25 + 1.1 * ring_phase)
            ring_a = (1.0 - ring_phase) * 0.9 * alpha
            if ring_a > 0.02:
                renderer.draw_shaded_3d(
                    _ring(x, y, profile, ring_r, radius * float(params["ring_thickness"]),
                          colors["disc"], ring_a), ground_additive, True)

        # Emitters: borrow handles on first sight, then feed them. Feeding is also what keeps the
        # C++ side alive -- an emitter that stops being fed clears itself.
        wanted = len(preset.emitters)
        handles = self._lent.get(key)
        if handles is None or len(handles) != wanted:
            if handles:
                self._give_back(handles)
            handles = self._take(wanted)
            self._lent[key] = handles
        for emitter, handle in zip(preset.emitters, handles):
            self._apply_emitter(handle, emitter)
            handle.set_origin(x, y, gz)

    def end_frame(self) -> None:
        """Release every beacon that was not shown. Call once per frame, after all ``show`` calls."""
        if not self.frozen:
            self._frame += 1
        for key in [k for k in self._lent if k not in self._seen]:
            self._give_back(self._lent.pop(key))
        self._seen.clear()

    def clear(self) -> None:
        """Drop everything -- every beacon and the whole pool."""
        for key in list(self._lent):
            self._give_back(self._lent.pop(key))
        for handle in self._free:
            try:
                handle.clear()
            except Exception:
                continue
        self._free.clear()
        self._seen.clear()
        self._profiles.clear()

    def live_particles(self) -> int:
        """What the pool is actually simulating right now."""
        total = 0
        for handles in self._lent.values():
            for handle in handles:
                try:
                    total += handle.count()
                except Exception:
                    continue
        return total

    def active_beacons(self) -> int:
        return len(self._lent)


_renderer_instance: BeaconRenderer | None = None


def renderer() -> BeaconRenderer:
    """The shared renderer. One pool, so every consumer draws from the same handles."""
    global _renderer_instance
    if _renderer_instance is None:
        _renderer_instance = BeaconRenderer()
    return _renderer_instance
