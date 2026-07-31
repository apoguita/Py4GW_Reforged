# Fight Zone — behavioural specification

Exact behaviour of `HeroAI/fight/**`. Written to be read cold: every decision
order, threshold and invariant is stated rather than implied. Numbers are the
shipped defaults.

Companion to the integration notes; this document describes *what it does*, not
how it was ported.

---

## 1. Coordinate conventions

Two frames, and confusing them is the single easiest way to misread this code.

**World frame** — Guild Wars `(x, y)`. All agent positions, the anchor, and the
escape route live here.

**Formation-local frame** — origin at the anchor (the pin), `+fwd` along
`zone.facing` (toward the enemy), `+lat` to the left of it.

```python
fwd = (dx * cos(facing)) + (dy * sin(facing))
lat = (dy * cos(facing)) - (dx * sin(facing))
```

Formation pins are authored in this frame with **negative y meaning behind the
front line**. The front rank sits at `y = 0`, mid at `y = -320`, back at
`y = -620`. `midline_depth` and `backline_depth` are the *absolute values* of
those, so they are positive numbers describing depth behind the front.

Trigger rings are ellipses in this frame. A ring's `tip()` is `centre + fwd` —
its forward-most edge, and the depth at which it trips.

---

## 2. Where it runs

Leader-authoritative. Only the leader's client ticks the zone; followers never
compute anything.

```
leader tick
  └─ FollowFormationPublisher.publish()
       ├─ _resolve_fight_plan()  → FightZonePublisher.tick() → FightPlan | None
       │                              └─ tick_zone()  (the state machine)
       ├─ _apply_fight_all_flag()     writes zone anchor into leader AllFlag
       └─ per-member loop
            └─ _publish_fight_slot()  writes each member's FollowPos to shmem
```

Followers read `FollowPos` out of shared memory and walk to it with their normal
follow logic. There is no fight-specific follower code. A follower cannot tell a
fight slot from a follow slot except by the tolerance value attached to it.

---

## 3. Activation gates

`_resolve_fight_plan` returns `None` — meaning stock follow behaviour, unchanged
— in any of these cases, checked in this order:

1. `fight_zone_enabled` is false (default).
2. A **manual all-flag** exists: `leader_options.IsFlagged` and `AllFlag` is
   non-zero and `fight_owns_all_flag` is false. Assignment state is cleared.
3. `tick_zone` leaves the zone in a non-active state (`TRAVELING`).

Gate 2 is the important one. The zone writes its anchor into the same `AllFlag`
field the user's manual flag uses, because `HeroAIOptionStruct` is a C++-owned
shared-memory layout that cannot grow a field. `fight_owns_all_flag` is the only
thing distinguishing "we wrote this" from "the user did". Without it the zone
reads its own flag back as a manual one and permanently disables itself.

**A hand-placed party flag always outranks the zone.** That is the intended
manual override.

---

## 4. State machine

Four states. `tick_zone` is called once per publish tick.

| State | Meaning |
|---|---|
| `TRAVELING` | Inactive. No plan is produced. |
| `ENGAGING` | Pin placed, party moving into formation. |
| `HOLDING` | Formation formed; steady-state fighting. |
| `CLEARING` | Combat over, holding position through looting. |

### Transitions

```
TRAVELING ──party_in_aggro──────────────────────────────► ENGAGING
                                                          (reset ground, drop pin)

ENGAGING  ──members_in_position OR 6000ms elapsed───────► HOLDING
ENGAGING  ──not party_in_aggro─────────────────────────► CLEARING
HOLDING   ──not party_in_aggro─────────────────────────► CLEARING

CLEARING  ──party_in_aggro─────────────────────────────► ENGAGING
CLEARING  ──not loot_pending───────────────────────────► TRAVELING

any active ──leader >2500u from pin──┬─ still in aggro ─► ENGAGING (re-drop pin)
                                     └─ otherwise ──────► TRAVELING
```

Both `ENGAGING` and `HOLDING` run the same two operations each tick, in this
order: `should_reaim()` → maybe re-anchor, then `adjust_ground()`. The only
difference between the states is the exit condition.

**Entering `ENGAGING` from `TRAVELING`** resets `retreat_steps`, `advance`,
`hold_until_ms`, `giving_ground` and `closing`. A new fight starts at the
authored position.

**The abandon-and-re-drop path deliberately does *not* reset them.** That path is
the same fight continuing somewhere else, and ground already given still counts.
`CLEARING` exists so nobody wanders off mid-pickup.

---

## 5. Blob resolution

Enemy positions are clustered before anything reads them.

1. **Weld** every enemy within `blob_weld_distance` (500u) of another into one
   cluster (union-find, transitive).
2. **Select** the cluster containing the member *nearest the party centre*.
   That cluster is the *engagement blob*.
3. If clustering yields nothing, fall back to treating all enemies as one blob.

Everything downstream — facing, all three trigger rings, re-aim — reads the
engagement blob's **centroid**, never the all-enemy centroid.

> Mixing the two is a real bug that was fixed: with two mob groups on screen,
> an all-enemy centroid sits permanently hundreds of units from the blob
> centroid, so a test comparing them fires forever and re-clamps the anchor to
> the leader every tick.

A consequence worth stating: a lone puller closest to the party *is* the
engagement blob. The party will engage it rather than the pack behind it. That
is intended.

---

## 6. Anchor and facing

The anchor is placed once per re-aim, not per tick.

1. `blob_centre` = centroid of the engagement blob.
2. `engagement` = `blob_centre`, clamped so it is never more than
   `max_anchor_offset_from_party` (600u) from the party centre.
3. `facing` = `compute_axis(...)` — the party→blob bearing, blended 35% toward
   the reversed escape route bearing when the two are within 60°. If the blob is
   closer than `min_facing_baseline` (322u) the bearing is noise, so the previous
   facing is held.
4. `pin` = `engagement` pulled back along facing by `engagement_standoff` (400u).
5. The pin is **never allowed to move backwards** relative to the current one
   during a re-aim. A backwards component is banked into `zone.advance` instead.

Step 5 matters: standing off from a blob that has *arrived* at the front line
would otherwise place the pin behind where the front rank already stands, and the
formation would walk backwards through its own casters.

---

## 7. The re-aim gate

`should_reaim()` decides whether to re-place the anchor. It is deliberately
reluctant. Evaluated in this exact order — earlier checks short-circuit:

1. **No stored facing target** → `False` (nothing to compare against).
2. **Build the approaching set**: enemies further than `contact_radius` (322u)
   from the engagement point. If empty → reset pending, return `False`.
   Enemies already at contact tell you nothing about where to stand; judging on
   them lets a charging melee mob walk the formation backwards as it closes.
3. **Re-cluster the approaching set** and take its size. Window scaling comes
   from this size, not the total enemy count.
4. **Forced re-aim**: if the blob just shrank *down through* 3 or 1
   (`force_reaim_at_sizes`), fire immediately. A first measurement
   (`previous <= 0`) never counts — arriving at a size is not falling to it.
   This is checked **before** the geometry test, because killing one of three
   moves the centroid ~150u, which the lateral gate is built to ignore.
5. **Geometry**: compute the proposed axis; `swing` = angle between it and
   current facing; `drift` = distance the blob centroid moved.
   `lateral = drift * sin(min(swing, 90°))`.
   Qualifies if `swing ≥ 28° AND lateral ≥ 250u`, or `drift ≥ 700u`
   (`facing_rehome_distance`). Otherwise reset pending, return `False`.
6. **Commit window**: the condition must hold continuously for
   `1500ms × commit_tier`.
7. **Recompute floor**: at least `4000ms × floor_tier` since the last re-aim.
   This is a floor, not a rejection — `pending` is left standing so the re-aim
   fires the instant the floor expires rather than restarting confirmation.

Only the **lateral** component counts. Movement straight along the axis is a mob
closing or backing off, which never justifies turning the formation.

### Slowdown tiers

Indexed by blob size, clamped to `[1, 4]`:

| Blob size | Commit window | Recompute floor |
|---:|---:|---:|
| 1 | 4500 ms | **24000 ms** |
| 2 | 3750 ms | 16000 ms |
| 3 | 3000 ms | 10000 ms |
| 4+ | 1500 ms | 4000 ms |

Small blobs have the twitchiest centroids, so they are trusted least.

**This is why the trigger rings must be ellipses.** With a 24-second floor, the
facing in use can be badly stale, and a blob that has slid off-axis is
under-read by any test that projects onto the facing axis alone. The lateral
radius is what closes that blind spot. Narrowing it re-opens the bug.

---

## 8. Trigger rings

Three ellipses in the formation-local frame. Membership test:

```python
((fwd - ring.centre) / ring.fwd)**2 + (lat / ring.lat)**2 < 1.0
```

A ring with `fwd <= 0` or `lat <= 0` contains nothing.

### Geometry (default formation: `midline_depth` 320, `backline_depth` 620)

| Ring | centre | fwd | lat | tip | floor |
|---|---:|---:|---:|---:|---:|
| Backline | −620 | 322 | 450 | **−298** | −942 |
| Midline | −400 | 240 | 900 | **−160** | −640 |
| Frontline | +218 | 538 | 1012 | **+756** | −320 |

**Backline** is centred on the rear rank (`-backline_depth`), so it follows the
authored formation.

**Midline** has its tip pinned at `-overrun_depth`, where
`overrun_depth = midline_depth * 0.5` — halfway between the front and mid ranks,
i.e. −160. A trigger *at* the mid rank fires only once the casters are already
being walked through. Halfway sits behind honest front-line wrap, and one
`give_ground_step` still clears it, so the trigger is self-releasing.

**Frontline** is static — it describes *reach*, not formation shape. Its floor
lands on the mid rank (218 − 538 = −320) so nothing level with or behind the
casters votes on advancing. Furthest point from the pin is 1044u, inside the
1248u scan radius, so no part of it tests ground where an enemy could not be
detected.

### Escalation clamp — load-bearing, not cosmetic

`backline_ring()` clamps its own tip to at most
`midline_ring().tip() - ring_escalation_margin` (100u).

`backline_ring_fwd` is a fixed 322 while the rank it sits on comes from the
formation. On a compressed formation — say `backline_depth = 310` — the unclamped
tip lands at **+12**, *in front of the pin* and ahead of the midline trip. The
emergency would fire before the soft step ever got a chance. On the default
formation the clamp is inert: the gap is 138u against a 100u margin.

### The three tests

| Test | Reads | True when |
|---|---|---|
| `backline_breached` | blob centroid | inside the backline ring |
| `overrun` | blob centroid | inside the midline ring |
| `frontline_reached` | blob centroid | inside the frontline ring |

All three read the centroid. `frontline_reached` returns `False` when there is no
blob at all, so an empty field keeps closing armed.

---

## 9. Ground control

`adjust_ground()` — the whole movement policy. Exact order:

```
1. breached = backline_breached(...)          # latched to zone.breached
2. if not breached and now < hold_until_ms:   return    # dwell blocks everything else
3. if breached or overrun(...):               RETREAT one step
4. elif not frontline_reached(...):           ADVANCE one step
5. else:                                      HOLD
```

A breach **outranks the dwell** — it is the only thing that can move the pin
before `hold_until_ms`. Everything else waits.

### Retreat

- Step size: `min(give_ground_step, ceiling - given_ground)` where
  `ceiling = min(max_given_ground 1400, retreat_distance - give_ground_margin 200)`.
- Direction: one step along the **escape route's local heading at the party's
  current position** — never the whole displacement measured against the route.
  The route is replotted every second from a moving party centre, so its bearing
  wobbles; measuring the full withdrawal against it each tick multiplied that
  wobble by how far the party had already withdrawn and walked the formation
  around all fight. Stepping means a replot can only affect the next step.
- If `advance > 0`, the step is taken out of `advance` first; only once that is
  spent does it push onto the `retreat_steps` stack.
- Dwell after: `breach_hold_ms` (1000) if breached, else
  `recover_hold_tiers_ms` indexed by blob size.

### Advance

- Step size: `give_ground_step` (250u) along facing.
- Retreat steps are **popped in reverse order** before any new ground is taken.
  Popping the stack is what retraces a dogleg withdrawal through the corner it
  went round instead of cutting across it.
- Dwell after: flat `advance_hold_ms` (4000), at every blob size.

250u per 4s is roughly 22% of run speed — a deliberate creep onto a camped mob,
not a charge.

### Dwell tiers

| Blob size | Retreat dwell |
|---:|---:|
| 1 | 18000 ms |
| 2 | 12000 ms |
| 3 | 7500 ms |
| 4+ | 5000 ms |

Retreat is tiered; advance is not. Backing up must never become a slide, and the
tail of a fight is the twitchiest reading. An early advance step is walked off by
the next one; an early retreat compounds.

### Self-limiting by construction

Both directions drag their own trigger with them. One retreat step moves the
midline ring back 250u, which clears a −160 trip. One advance step drags the
frontline ring 250u onto the mob. Neither needs a timer to stop.

**The formation translates and never rotates during ground adjustment.** Enemies
stay squarely in front however far it moves; facing is decided only in §6.

---

## 10. Formation, lines and assignment

### Default formation (local frame)

| Line | Pins | y | Tolerance |
|---|---|---:|---:|
| FRONT | x = −160, 0, 160 | 0 | 120 |
| MID | x = −260, −90, 90, 260 | −320 | **300** |
| BACK | x = −180, 0, 180, 360 | −620 | 150 |

Mid tolerance is deliberately wide so the build's own kiting owns movement rather
than fighting the zone for it.

### Depth budget

```
max_depth = max(200, CAST_RANGE(1248) - CAST_SAFETY_MARGIN(100) - front_tol - back_tol)
          = max(200, 1248 - 100 - 120 - 150) = 878
```

The default depth is 620, so no clamp applies. An over-deep authored formation is
compressed along Y at runtime rather than trusted, because a back rank out of
cast range of the front is a formation that cannot heal itself.

### Line resolution, in precedence order

1. **Manual override** (`LineSource.MANUAL`) — `FightLines.ini`, keyed by
   *character name*. Party position shuffles, and an account email does not
   distinguish two characters on one account. Followers re-read this on a
   throttle, so a leader-side reassignment lands within a second without a
   restart.
2. **Build-declared line** (`LineSource.BUILD`), if the loaded build declares one.
3. **Profession inference** (`LineSource.INFERRED`): Warrior / Assassin / Dervish
   / Paragon → FRONT; Monk / Ritualist → BACK; everything else → MID.

Any level returning `AUTO` falls through to the next.

### Spill

When a line has more members than pins, the overflow goes to the next line in
`SPILL_ORDER`:

| Line | Spills to, in order |
|---|---|
| FRONT | MID, then BACK |
| MID | BACK, then FRONT |
| BACK | MID, then FRONT |

Front and back both spill **inward** — the midline is the most forgiving place to
stand. `SlotPlan.requested_line` records what was asked for and `line` what was
granted, so a spill is visible in the UI rather than silent.

**Assignment is latched, not recomputed per tick.** It is rebuilt only when the
composition signature — the sorted set of `(party_position, line)` pairs —
changes. A death must not reshuffle everyone mid-fight.

---

## 11. Escape route

Replotted at most once per second. Two candidate sources, scored against each
other:

**Radial scan** — 24 rays at 15°, probed in 160u steps against
`navmesh.contains`, capped at `Spellcast` (1248u). Covers the full circle
deliberately, not just the retreat arc: against a wall the only opening is often
forward or along it.

**Breadcrumb backtrack** — the party's own footprints, budgeted by *distance* out
to `Compass` (5000u). Walkable by construction, correct about doglegs, and
available even when the navmesh is not. Gets a `trail_confidence` bonus of +0.25,
which makes it the default answer and the scan the fallback.

Scoring terms: openness, clearness of the far half of the route, alignment away
from the enemy mass, alignment toward the last safe spot, and stickiness to the
previous axis. Weights are ordered by how much each term actually *varies*, not
by importance — `home_weight` is small (0.35) because home alignment swings the
full 0..1 across a circle of candidates while clearness rarely swings half that.
At equal weights, "roughly homeward" outvotes "not full of enemies" and the route
plots a diagonal through the pack.

Threat is sampled only over the far half of the route: enemies standing on the
party are equally close to every candidate and discriminate nothing.

The trail joins at its **nearest** crumb, not its newest. The newest crumb is
between the party and the fight after any withdrawal, so starting there marched
the route forward into the enemies before turning around.

---

## 12. Configuration

Section `FightRuntime`, via `Settings`.

| Key | Default | Effect |
|---|---|---|
| `fight_zone_enabled` | `False` | Master switch |
| `show_fight_zone_overlay` | `False` | 3D debug overlay |
| `fight_zone_overlay_circles_only` | `False` | Draw only armed rings |
| `engage_depth_u` | `538.0` | → `frontline_ring_fwd`, clamped to [250, 900] |

`FightLines.ini` holds per-character manual line overrides.

**A saved `engage_depth_u` wins over the source default.** Changing the default in
code has no effect on an installation that already has a saved value.

---

## 13. Invariants

Breaking any of these produces behaviour that looks plausible and is wrong.

1. **Midline tip is always forward of backline tip.** Enforced by the clamp in
   `backline_ring()`, not by configuration. Inverting it makes the emergency fire
   before the soft step.
2. **All ring tests read the engagement blob centroid**, never the all-enemy
   centroid and never individual enemies.
3. **Rings are ellipses.** The lateral axis exists because facing can be up to
   24s stale. Replacing them with depth planes, or narrowing `lat`, restores the
   off-axis blind spot.
4. **`fight_owns_all_flag` gates every write to `AllFlag`.** Without it the zone
   reads its own flag as a manual one and disables itself permanently.
5. **The pin never moves backwards on re-aim.** Backwards components are banked
   into `advance`.
6. **Retreat steps are a stack, popped in reverse.** Replacing the stack with a
   scalar distance loses the dogleg.
7. **Only the step is read off the escape route**, never the accumulated
   displacement.
8. **`HeroAI/fight/__init__.py` stays empty.** `SharedMemory` imports
   `leader_publish` during startup and `HeroAI.fight` pulls `AgentArray`; a
   package-root import closes the cycle.
9. **The overlay reads only the published snapshot dict.** `ui_base` importing
   from `HeroAI.fight` at module scope would couple UI to engine startup.

---

## 14. Observable state

`hero_globals.fight_zone_debug_snapshot`, a plain dict rewritten once per tick.
This is the entire debugging surface and the only thing the UI reads.

| Key | Meaning |
|---|---|
| `state` | `ZoneState` name |
| `anchor`, `facing` | Pin position and heading |
| `rings` | `{name: (centre, fwd, lat)}` — as enforced, not raw rank depths |
| `blob`, `blob_depth` | Engagement blob centroid, and its depth along facing |
| `overrun`, `breached` | Midline / backline ring armed |
| `closing_armed` | `not frontline_reached` — advance is armed |
| `giving_ground`, `closing` | Current movement intent |
| `given_ground`, `advance` | Accumulated distance in each direction |
| `reaim_blob_size`, `reaim_commit_ms`, `reaim_floor_ms` | Live re-aim windows |
| `forced_reaims` | Count of size-threshold forced re-aims |
| `escape` | Route origin, waypoint, distance, source, polyline |
| `escape_boxed_in` | A plot ran *with terrain data* and found nothing |
| `escape_terrain_known` | Whether a navmesh probe was available at all |
| `slots` | Per-member pins — **wanted positions, not resolved ones** |
| `depth_clamped` | The formation was compressed to fit the reach budget |

`escape_boxed_in` and `escape_terrain_known` are separate on purpose: "we
searched and are trapped" and "we had no map" are different facts and the UI
words them differently.

---

## 15. Known deviations from ideal

Present in the shipped code. Listed so they are not mistaken for bugs to
opportunistically "fix" without understanding the trade.

1. **The anchor is not navmesh-validated.** Member pins go through
   `resolve_placement` (standable *and* reachable). The anchor written to
   `AllFlag` does not, and neither does the forward advance step — all terrain
   machinery currently looks backwards along the escape route.
2. **`slots` in the snapshot are pre-resolution.** Navmesh nudging happens
   downstream in `leader_publish` and its result goes only to shared memory, so
   a pin drawn inside a wall does not mean a follower stands there.
3. **A pack straddling the frontline ring averages out beyond it**, so the front
   rank is already in contact before `frontline_reached` becomes true. This is a
   deliberate choice: the alternative — requiring the ring to be *empty* — let a
   single straggler pin the whole party in place.
4. **Retrace reports the wrong label.** Popping retreat steps leaves
   `giving_ground=True, closing=False`, so the UI reads "BACKING OFF" while the
   pin moves forward. Cosmetic only.
5. **`has_line_of_sight` samples interior points only.** Any hop shorter than the
   step distance has no samples and returns `True` unconditionally, so
   short-range reachability results carry no information.
