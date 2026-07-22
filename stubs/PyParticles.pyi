# PyParticles stub - Reforged Native surface.
# Matches particle_system_bindings.cpp. C++ runs the simulation; Python only
# configures via EmitterConfig. Emitters are camera-facing billboard quads
# (no textures), drawn occluded in the world pass.

# Emit modes (EmitterConfig.mode). Bound as plain module int attributes, not an enum.
BALLISTIC: int   # = 0; dir/speed/spread + gravity/drag  -> geyser / sparks / fountains
ORBITAL: int     # = 1; radius/spin/rise                 -> swirl / vortex / halos

class EmitterConfig:
    # Every field is a live read/write property; set e.config.<field> = ...
    enabled: bool           # emitter on/off
    mode: int               # BALLISTIC or ORBITAL
    max_particles: int      # hard pool cap
    rate: float             # continuous emission, particles/sec (0 = burst only)

    origin_x: float         # emitter origin (world; up = -z). Usually set via set_origin().
    origin_y: float
    origin_z: float

    dir_x: float            # launch direction (up = -z)
    dir_y: float
    dir_z: float
    speed: float            # launch speed
    speed_var: float        # +/- speed variance
    spread: float           # cone half-angle, radians (0 = beam .. pi = full sphere)

    grav_x: float           # gravity/accel (up = -z, so +z pulls down)
    grav_y: float
    grav_z: float
    drag: float             # velocity damping per second

    orbit_radius: float     # ORBITAL: ring radius
    orbit_radius_var: float
    orbit_radius_end: float # radius at end of life (<0 = constant)
    orbit_spin: float       # radians/sec around the vertical axis
    orbit_rise: float       # climb speed (world units/sec, upward)
    orbit_height: float     # climb this far, then recycle

    spawn_radius: float     # spawn within a ground disc of this radius around origin
    radial_speed: float     # extra outward horizontal launch speed (nova / shockwave)
    turbulence: float       # random velocity jitter (organic wander -> fire / smoke)
    stretch: float          # velocity-aligned streak factor (0 = round billboard)

    life: float             # particle lifetime, seconds
    life_var: float
    size: float             # billboard size
    size_var: float
    size_end: float         # size at end of life
    color: int              # ARGB at spawn
    color_end: int          # ARGB at end of life
    hot_frac: float         # fraction of particles spawned white-hot
    additive: bool          # additive (light) vs alpha blend

class ParticleEmitter:
    config: EmitterConfig   # live config; set any field, e.g. e.config.rate = 60
    # Move the origin (world; up = -z). Call each frame to attach to a target.
    # Also FEEDS the 100ms timeout: stop calling it (or keepalive) and the emitter
    # clears + stops; resumes when fed again.
    def set_origin(self, x: float, y: float, z: float) -> None: ...
    def keepalive(self) -> None: ...            # feed the timeout without moving (static effects)
    def emit(self, count: int) -> None: ...     # spawn a burst of `count` particles now
    def clear(self) -> None: ...                # kill all current particles
    def count(self) -> int: ...                 # live particle count

# Create a system-managed emitter. HOLD the returned object to keep the effect
# alive; when it is dropped (or the script stops) the effect stops and frees.
def create_emitter() -> ParticleEmitter: ...
def shutdown() -> None: ...                     # remove all emitters and unregister the draw
