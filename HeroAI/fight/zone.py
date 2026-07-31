"""Fight zone lifecycle: an auto-dropped party pin with a state machine."""

from __future__ import annotations

import math
from dataclasses import dataclass
from dataclasses import field
from enum import IntEnum

from Py4GWCoreLib import Range

from .breadcrumbs import sample_at


class ZoneState(IntEnum):
    TRAVELING = 0
    ENGAGING = 1
    HOLDING = 2
    CLEARING = 3


@dataclass(slots=True)
class ZoneConfig:
    # How far from the pin still counts as "in the zone".
    engage_radius: float = float(Range.Spellcast.value)
    # Leader beyond this from the pin means the pin is stale. Matches
    # FOLLOW_RECOVERY_DISTANCE so zone abandon and follow recovery agree.
    abandon_distance: float = float(Range.Spirit.value)
    # The pin is placed at the enemy centroid but never dragged further than
    # this from the PARTY's centre of mass — a stray far-off enemy must not yank
    # the formation off the body of the team.
    #
    # Measured from the party, not the leader. Anchoring on the leader pinned
    # the whole formation to one member: the front line could never be more than
    # this minus the standoff ahead of them, so a party whose leader stood still
    # could not close on anything, however much it wanted to. The party's own
    # mass is what the formation is built around, and it moves with the fight.
    max_anchor_offset_from_party: float = 600.0
    # How far BACK along the approach the pin sits from the engagement point.
    # Anchoring on the enemy centroid itself plants the front line inside the
    # mob and drags every line forward with it, so the backline ends up doing
    # its work at midline range. Standing off keeps the whole formation behind
    # the contact point, where it was authored to be.
    engagement_standoff: float = 400.0
    # Enemies within this of each other are one blob. A mob group is what you
    # fight; the centroid of two separate groups points at empty ground between
    # them.
    blob_weld_distance: float = 500.0
    # How far the retreat axis may pull the blob axis. Past this the two
    # disagree enough that something is wrong with the reading — being ganked
    # from behind is the obvious case — and the enemies win outright.
    max_approach_blend_rad: float = math.radians(60.0)
    # Weight of the retreat axis inside that cone. Small: the blob decides where
    # "in front" is, the retreat only biases which way the backline sits.
    approach_blend: float = 0.35
    # A blob centroid closer than this to the party centroid gives no usable
    # direction. It sits INSIDE the formation, so the bearing to it is decided
    # by which enemy happens to have shuffled, and one step flips it by a
    # half-turn. The formation then rotates about its own middle and the
    # backline — a full 620u out along -facing — is thrown bodily through
    # whatever is standing there.
    #
    # Sized against the default formation: the party centroid sits ~310u behind
    # the front line, so enemies in honest melee contact are right at this
    # distance. Holding the last good axis through contact is correct anyway —
    # the fight is where it already is, and re-deriving a heading from a
    # centroid standing on top of you is how the spin starts.
    min_facing_baseline: float = float(Range.Area.value)
    # Enemies further than this from the leader are not part of this engagement.
    engagement_scan_radius: float = float(Range.Spellcast.value)
    # ENGAGING gives up and holds anyway; a blocked member must not wedge the party.
    engage_timeout_ms: int = 6000
    # Re-aim gate. Angle rather than distance is the primary test because
    # distance gets scale backwards: a blob 2000u away sliding 400u barely moves
    # the axis, while the same 400u at close range flips it.
    reaim_angle_threshold: float = math.radians(28.0)
    # Angle alone is scale-invariant, which is backwards up close: 100u of
    # shuffle is 27deg at 200u range but 5deg at 1200u, so melee fights re-aim
    # far more than ranged ones. Requiring a real lateral displacement too makes
    # the two gates cover each other's blind spot — near-field jitter fails the
    # lateral test, far-field drift fails the angle test.
    reaim_min_lateral: float = 250.0
    # Enemies this close to the contact point have ARRIVED. A melee mob closing
    # on the front line is not the fight moving somewhere else — it is the fight
    # working exactly as expected — so it must not drag the formation around.
    #
    # Measured from the contact point, which is at the FRONT. The known cost is
    # that an enemy which walked around onto the backline reads as a new threat
    # elsewhere and drives a full re-aim, interrupting casts.
    #
    # The standing candidate fix — measure from the party centroid instead — is
    # REJECTED. Measuring from the front is what gives the formation its fallback
    # under a rush: enemies that close onto the party stay outside this radius,
    # so they still count as approaching, the engagement point follows them onto
    # the party, and engagement_standoff then plants the pin behind it. The party
    # gives ground and the backline gets its range back. Measuring from the party
    # centroid filters exactly those enemies out and the fallback collapses (413u
    # of ground given vs 173u, ending in front of the party rather than behind
    # it). Bounded by construction at max_anchor_offset_from_party +
    # engagement_standoff from the leader, so it cannot rout.
    contact_radius: float = float(Range.Area.value)

    # Small blobs are unstable by construction: removing one of N shifts the
    # centroid by (centroid - dead) / (N - 1), so at N=3 a mob 300u out from the
    # centre moves it 150u on death, against 43u at N=8. Movement scales the same
    # way, so the tail of every fight is its twitchiest phase.
    #
    # Refusing to re-aim below a size threshold traded that twitch for a worse
    # failure: the last one or two enemies pull away, the pin is frozen where the
    # pack died, and the party fights the rest of it out of formation. Instead
    # the timing gates stretch as the blob shrinks — the formation keeps
    # re-forming all the way to the last kill, just progressively more slowly.
    #
    # The two gates are tiered separately because they charge for jitter in
    # different currencies. The floor is nearly free: it costs nothing on the
    # first move after a quiet spell and only caps how often a twitchy tail can
    # drag the formation, so it carries most of the slowdown. The commit window
    # delays every genuine relocation by its full length, so it stays close to
    # flat — a lone enemy that really walked off is answered in a few seconds,
    # not ten. Index 0 is a lone enemy; the last entry covers every size at or
    # above its own.
    reaim_commit_slowdown_tiers: tuple[float, ...] = (3.0, 2.5, 2.0, 1.0)
    reaim_floor_slowdown_tiers: tuple[float, ...] = (6.0, 4.0, 2.5, 1.0)
    # Distance still catches the one case angle cannot see — a mob retreating
    # straight down the axis, where the bearing never changes but the fight has
    # walked away. Deliberately large: this is for relocation, not jitter.
    facing_rehome_distance: float = 700.0
    # The deviation must persist this long before it counts. Kills reaction to
    # a mob shuffling through the threshold and back.
    reaim_commit_ms: int = 1500
    # Hard floor on how often the formation may be re-aimed at all.
    min_facing_recompute_ms: int = 4000
    # Blob sizes that force a re-aim the instant the fight shrinks past them,
    # ahead of every gate above.
    #
    # The tiers make the tail of a fight the SLOWEST phase by construction — one
    # enemy buys a 4.5s confirm and a 24s floor — and it is also the phase where
    # the survivors are most likely to be somewhere else entirely. Damping is
    # the right answer while a pack is being fought and the wrong one once it is
    # down to stragglers: the party holds formation while two casters plink at
    # it from across the room. Crossing DOWN through a size is the trigger, so
    # this fires twice a fight, not every tick, and a fresh wave re-arms it.
    force_reaim_at_sizes: tuple[int, ...] = (3, 1)

    # One step per interval, so the party walks back and the mob follows in a
    # column. Giving the whole budget at once abandons a fight that was being
    # won and outruns the enemies instead of gathering them.
    # One backup is a single deliberate move, not a slide. 150u steps read as
    # the formation continuously drifting away from a fight it is still in.
    give_ground_step: float = 250.0
    # ...and then it SITS. Giving ground only helps if the party is still long
    # enough for heals to land and for the mob to re-form in front; stepping
    # again on the next tick is how a withdrawal turns into a rout that never
    # stops. Nothing moves, in either direction, until the dwell expires.
    #
    # RETREAT dwell is authored per blob size, same shape as the re-aim tiers:
    # index 0 is a lone enemy, the last entry covers every size at or above its
    # own. Small blobs are the twitchiest centroids, so the tail of a fight
    # gives ground the most rarely. Backing up is the move that must never
    # become a slide, so it keeps the tiering.
    recover_hold_tiers_ms: tuple[float, ...] = (18000.0, 12000.0, 7500.0, 5000.0)
    # ADVANCE is flat, and deliberately not tiered. Tiering it inverted: tier_for
    # clamps with max(size, 1), so zero enemies read as a lone enemy and drew the
    # slowest dwell of all, at exactly the moment there was nothing left to be
    # careful about. A jittery centroid is also self-correcting forwards in a way
    # it is not backwards — an early step is walked off by the next one, where an
    # early retreat compounds. 250u every 4s is ~22% of run speed: a deliberate
    # creep onto a camped mob, not a charge.
    advance_hold_ms: int = 4000
    # Hard ceiling on ground given, in route metres. The route's own length is
    # the usual limit; this is the backstop. Sized against abandon_distance:
    # the pin sits at most max_anchor_offset_from_party + engagement_standoff
    # from the leader before any retreat, so 1400 keeps the worst case inside
    # 2500 and the zone cannot tear itself down by retreating.
    max_given_ground: float = 1400.0
    # Never withdraw onto the far end of the route, where the next step would
    # have nowhere to go and a re-plot could leave the pin off the path.
    give_ground_margin: float = 200.0
    # --- trigger rings -------------------------------------------------------
    # The three tests below run on ELLIPSES in the formation's local frame
    # rather than on flat depth planes. Depth alone is a projection onto the
    # facing axis, which throws the lateral component away entirely; that is
    # tolerable only while facing points at the blob, and facing is gated on
    # purpose (reaim_commit_ms, min_facing_recompute_ms, and slowdown tiers that
    # stretch the floor to 24s for a lone enemy). Through those hold windows the
    # blob slides off-axis and the projection under-reads it. A ring does not
    # care where the formation is looking.
    #
    # Each ring is (centre, fwd, lat) along facing. `fwd` sets how deep it
    # reaches; `lat` is a free knob for wrap-around that cannot move the forward
    # trigger. That separation is the whole reason for authoring them this way.
    #
    # Midline: the soft trip. Its forward tip lands at overrun_depth, so the
    # trigger DEPTH is unchanged from the flat-plane version it replaces and the
    # only new behaviour is lateral.
    midline_ring_fwd: float = 240.0
    midline_ring_lat: float = 900.0
    # Backline: the panic ring, centred on the rear rank. Area-deep so its tip
    # sits ~300u in front of the casters, well behind the midline trip — the two
    # must stay in that order or the emergency fires before the soft step.
    backline_ring_fwd: float = float(Range.Area.value)
    backline_ring_lat: float = 450.0
    # Minimum daylight between the midline tip and the backline tip. Must stay
    # under the 138u the default formation already has, or the clamp in
    # backline_ring would bite on a formation that was ordered fine.
    ring_escalation_margin: float = 100.0
    # Frontline: where the party can still find a fight. Static rather than
    # derived, because it describes REACH, not formation shape.
    #
    # `fwd` is set so the floor lands on the mid rank (218 - 538 = -320): behind
    # that is the midline ring's business, and anything level with or behind the
    # casters should not be deciding whether the party advances. The ceiling
    # follows at +756. Deliberately flat rather than small — `lat` stays at
    # Earshot, because narrowing it is what stops a mob wrapping the flank from
    # registering, and that is the failure worth avoiding. The furthest point
    # from the pin is 1044u against a 1248 scan, so no part of the ring tests
    # ground where an enemy could never be detected.
    #
    # The cost is early warning: the party now looks 756u ahead rather than 948
    # before concluding there is nothing to fight, so a pack camped beyond that
    # reads as empty ground and gets walked at.
    #
    # `fwd` is tunable live from the Fight Lines tab; the publisher clamps and
    # applies engage_depth_u from FightRuntime.ini on its reload timer, and a
    # saved value there WINS over this default.
    frontline_ring_centre: float = 218.0
    frontline_ring_fwd: float = 538.0
    frontline_ring_lat: float = float(Range.Earshot.value)
    # A backline breach bypasses the recover dwell — waiting out 18s with a mob
    # standing on the monks is what the ring exists to prevent — but it must not
    # become a per-tick slide either, so it sets this instead. max_given_ground
    # and the route length still cap the total.
    breach_hold_ms: int = 1000


ZONE_CFG = ZoneConfig()


@dataclass(slots=True)
class FightZone:
    state: ZoneState = ZoneState.TRAVELING
    anchor_x: float = 0.0
    anchor_y: float = 0.0
    facing: float = 0.0
    radius: float = 0.0
    entered_state_ms: int = 0
    last_facing_target: tuple[float, float] | None = None
    last_facing_ms: int = 0
    # Point of contact. The pin sits engagement_standoff behind this.
    engagement_x: float = 0.0
    engagement_y: float = 0.0
    # When the re-aim deviation first went over threshold. 0 = not pending.
    reaim_pending_since_ms: int = 0
    # Size of the blob the last re-aim test ran against, and the two windows that
    # size bought it. Reported, not used — the overlay has no other way to say
    # why a stale-looking pin is behaving correctly.
    reaim_blob_size: int = 0
    reaim_commit_window_ms: float = 0.0
    reaim_floor_ms: float = 0.0
    # Blob size at the previous measurement, so a threshold can be detected as a
    # crossing. A level test ("size <= 3") would re-aim on every tick of the
    # endgame and never let a cast finish.
    last_blob_size: int = 0
    forced_reaim_count: int = 0
    # How far along the escape route the formation has withdrawn. Ratchets up
    # while the party is losing and resets when it recovers or the fight ends.
    # Each withdrawal step as a LATCHED world vector. A list rather than a
    # running total so coming back RETRACES the way out instead of cutting the
    # corner off a dogleg. Deriving the displacement from the live route instead
    # re-measured it against a freshly plotted path every second, and the
    # formation chased the wobble.
    retreat_steps: list[tuple[float, float]] = field(default_factory=list)
    # Ground taken PAST the authored position, along facing. Only ever nonzero
    # once every retreat step has been given back.
    advance: float = 0.0
    # Nothing moves in either direction until this expires.
    hold_until_ms: int = 0
    giving_ground: bool = False
    closing: bool = False
    # Blob centre of mass is inside the backline ring. Latched each tick so the
    # tab can show the emergency without recomputing the test.
    breached: bool = False

    def is_active(self) -> bool:
        return self.state != ZoneState.TRAVELING

    def anchor(self) -> tuple[float, float]:
        return (self.anchor_x, self.anchor_y)


def centroid(points: list[tuple[float, float]]) -> tuple[float, float] | None:
    if not points:
        return None
    return (
        sum(p[0] for p in points) / len(points),
        sum(p[1] for p in points) / len(points),
    )


def clamp_toward(
    point: tuple[float, float],
    origin: tuple[float, float],
    max_distance: float,
) -> tuple[float, float]:
    dx = point[0] - origin[0]
    dy = point[1] - origin[1]
    distance = math.hypot(dx, dy)
    if distance <= max_distance or distance <= 0.001:
        return (float(point[0]), float(point[1]))
    scale = max_distance / distance
    return (origin[0] + (dx * scale), origin[1] + (dy * scale))


def blend_angle(previous: float, target: float, alpha: float) -> float:
    """Shortest-arc blend. Averaging raw angles wraps at +-pi."""
    sin_part = (math.sin(previous) * (1.0 - alpha)) + (math.sin(target) * alpha)
    cos_part = (math.cos(previous) * (1.0 - alpha)) + (math.cos(target) * alpha)
    if abs(sin_part) < 1e-9 and abs(cos_part) < 1e-9:
        return target
    return math.atan2(sin_part, cos_part)


def angle_difference(left: float, right: float) -> float:
    return abs(math.atan2(math.sin(left - right), math.cos(left - right)))


def cluster_enemies(
    positions: list[tuple[float, float]],
    weld_distance: float,
) -> list[list[tuple[float, float]]]:
    """Group enemies whose weld radii overlap into blobs (union-find)."""
    count = len(positions)
    if count == 0:
        return []
    parent = list(range(count))

    def find(index: int) -> int:
        root = index
        while parent[root] != root:
            root = parent[root]
        while parent[index] != root:
            parent[index], index = root, parent[index]
        return root

    threshold = weld_distance * weld_distance
    for i in range(count):
        for j in range(i + 1, count):
            dx = positions[i][0] - positions[j][0]
            dy = positions[i][1] - positions[j][1]
            if (dx * dx) + (dy * dy) < threshold:
                root_i, root_j = find(i), find(j)
                if root_i != root_j:
                    parent[root_i] = root_j

    groups: dict[int, list[tuple[float, float]]] = {}
    for i in range(count):
        groups.setdefault(find(i), []).append(positions[i])
    return list(groups.values())


def select_engagement_blob(
    clusters: list[list[tuple[float, float]]],
    origin: tuple[float, float],
) -> list[tuple[float, float]] | None:
    """The blob we are actually fighting: the one with the nearest member."""
    best: list[tuple[float, float]] | None = None
    best_distance = float("inf")
    for cluster in clusters:
        for x, y in cluster:
            distance = math.hypot(x - origin[0], y - origin[1])
            if distance < best_distance:
                best_distance = distance
                best = cluster
    return best


def apply_standoff(
    engagement_xy: tuple[float, float],
    facing: float,
    standoff: float,
) -> tuple[float, float]:
    """Pull the pin back down the approach axis from the point of contact."""
    return (
        engagement_xy[0] - (math.cos(facing) * standoff),
        engagement_xy[1] - (math.sin(facing) * standoff),
    )


def resolve_engagement_blob(
    cfg: ZoneConfig,
    party_xy: tuple[float, float],
    enemy_positions: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    blob = select_engagement_blob(cluster_enemies(enemy_positions, cfg.blob_weld_distance), party_xy)
    return list(blob) if blob else list(enemy_positions)


def compute_axis(
    zone: FightZone,
    cfg: ZoneConfig,
    party_xy: tuple[float, float],
    approach_xy: tuple[float, float] | None,
    blob_centre: tuple[float, float],
    engagement_xy: tuple[float, float],
    retreat_axis: float | None = None,
) -> float:
    """Blob axis, nudged toward the way out, inside the cone.

    Shared with should_reaim on purpose: comparing a blended current facing
    against an unblended proposal would leave a permanent offset the size of the
    blend, and the gate would either never fire or fire constantly.
    """
    if math.hypot(blob_centre[0] - party_xy[0], blob_centre[1] - party_xy[1]) < cfg.min_facing_baseline:
        # Nothing to re-derive from. Hold the last good heading — unless there
        # is none, on which fresh zones depend, where a noisy axis still beats
        # whichever direction the previous fight happened to end on.
        if zone.last_facing_target is not None:
            return zone.facing

    blob_axis = math.atan2(blob_centre[1] - party_xy[1], blob_centre[0] - party_xy[0])

    # The rear of the formation should sit on the ground we intend to give, so
    # the escape route -- reversed, because it points outward -- is the better
    # reference. It falls back to the walked-in approach when no route is
    # plotted (no navmesh, or boxed in), which is what this always used.
    if retreat_axis is not None:
        advance_axis = retreat_axis + math.pi
    elif approach_xy is not None:
        advance_axis = math.atan2(engagement_xy[1] - approach_xy[1], engagement_xy[0] - approach_xy[0])
    else:
        return blob_axis

    if angle_difference(advance_axis, blob_axis) <= cfg.max_approach_blend_rad:
        return blend_angle(blob_axis, advance_axis, cfg.approach_blend)
    return blob_axis


def anchor_and_facing(
    zone: FightZone,
    cfg: ZoneConfig,
    leader_xy: tuple[float, float],
    party_xy: tuple[float, float],
    approach_xy: tuple[float, float] | None,
    enemy_positions: list[tuple[float, float]],
    now_ms: int,
    retreat_axis: float | None = None,
) -> tuple[float, float]:
    """Blob -> axis -> pin, computed only when the flag is (re)placed.

    The axis is taken from the party toward the nearest enemy blob, so that blob
    is in front of the pin by construction and front/mid/back project back from
    it. The approach path then nudges that axis inside a cone — it decides which
    way the backline leans, not where the front is. Outside the cone the two
    disagree too much to reconcile (ganked from behind is the obvious case) and
    the enemies win outright: facing the wrong way is worse than an odd retreat
    direction.
    """
    # Fresh placements (zone entry, abandon-redrop) clear this first, so it
    # cleanly distinguishes an in-fight re-aim, where the current pin position
    # is meaningful, from a drop where it is stale.
    reaiming = zone.last_facing_target is not None
    blob_centre = centroid(resolve_engagement_blob(cfg, party_xy, enemy_positions))

    # A blob sitting inside the formation gives no usable heading, and
    # compute_axis holds the last one. Relocating the pin onto it ANYWAY, and
    # then standing off 400u along that held heading, marches the formation away
    # from the mob by the standoff on every re-aim — the pin runs backwards
    # until the enemies are outside the zone and nothing can engage. When there
    # is no direction to be had, the honest move is not to move.
    if (
        blob_centre is not None
        and zone.last_facing_target is not None
        and math.hypot(blob_centre[0] - party_xy[0], blob_centre[1] - party_xy[1]) < cfg.min_facing_baseline
    ):
        zone.reaim_pending_since_ms = 0
        zone.last_facing_ms = now_ms
        return (zone.anchor_x, zone.anchor_y)

    engagement = (
        clamp_toward(blob_centre, party_xy, cfg.max_anchor_offset_from_party)
        if blob_centre is not None
        else (float(leader_xy[0]), float(leader_xy[1]))
    )

    if blob_centre is not None:
        zone.facing = compute_axis(zone, cfg, party_xy, approach_xy, blob_centre, engagement, retreat_axis)
        zone.last_facing_target = blob_centre
        zone.last_facing_ms = now_ms
    else:
        latch_facing(zone, engagement, approach_xy, leader_xy, enemy_positions, now_ms)

    zone.reaim_pending_since_ms = 0
    zone.engagement_x, zone.engagement_y = engagement
    # A re-aim REBASES: the offset is cleared, not carried.
    #
    # The engagement point is clamped to the party's own centre of mass, so it
    # already follows the party wherever a withdrawal has taken it. Carrying the
    # offset on top of that counts the same retreat twice, and it compounds —
    # back up, re-aim absorbs the move into the base, add the offset again, back
    # up from there. Within a few re-aims the formation is so far behind the
    # fight that the mob sits outside the zone entirely and nothing engages.
    #
    # This was correct while the clamp was on the LEADER, whose position does
    # not move when the party gives ground. It stopped being correct the moment
    # the reference became the party. Nothing lurches forward: the new base is
    # computed from where the party actually is now.
    zone.retreat_steps.clear()
    zone.advance = 0.0
    zone.giving_ground = False
    zone.closing = False
    pin = apply_standoff(engagement, zone.facing, cfg.engagement_standoff)
    # ...and never BACKWARDS. Standing off from a blob that has ARRIVED at the
    # front line puts the pin behind where the front line already stands, and
    # the mob follows every step: chase moves the blob centre past the rehome
    # threshold, that drift fires the next re-aim, and the standoff gives
    # another 400u — a treadmill that only stops when the mob leashes, parked
    # at the zone's edge with nothing engaging. Retreat is the ground
    # controller's call alone (midline breach, or hurt and in contact), so the
    # backwards component of a re-aim is banked as held ground instead of
    # walked; the rotation and lateral parts, which are what a re-aim is for,
    # still apply.
    if reaiming:
        forward_gap = ((zone.anchor_x - pin[0]) * math.cos(zone.facing)) + (
            (zone.anchor_y - pin[1]) * math.sin(zone.facing)
        )
        if forward_gap > 0.0:
            zone.advance = forward_gap
            pin = (
                pin[0] + (math.cos(zone.facing) * forward_gap),
                pin[1] + (math.sin(zone.facing) * forward_gap),
            )
    return pin


def compute_zone_facing(
    zone: FightZone,
    engagement_xy: tuple[float, float],
    approach_xy: tuple[float, float] | None,
    leader_xy: tuple[float, float],
    enemy_positions: list[tuple[float, float]],
) -> float:
    """The axis of advance: from where the party walked in, toward the fight.

    That is what puts the backline behind the party rather than wherever the
    leader happens to be facing — the retreat direction is the one they came
    from. Falls back to leader->enemies when the last safe spot sits too close
    to describe an approach (fresh zone-in, or ambushed while standing still).
    """
    if approach_xy is not None:
        dx = engagement_xy[0] - approach_xy[0]
        dy = engagement_xy[1] - approach_xy[1]
        if math.hypot(dx, dy) >= 0.001:
            return math.atan2(dy, dx)

    enemy_centroid = centroid(enemy_positions)
    if enemy_centroid is not None:
        dx = enemy_centroid[0] - leader_xy[0]
        dy = enemy_centroid[1] - leader_xy[1]
        if math.hypot(dx, dy) >= 0.001:
            return math.atan2(dy, dx)

    return zone.facing


def tier_for(tiers: tuple[float, ...], blob_size: int) -> float:
    if not tiers:
        return 1.0
    return tiers[min(max(blob_size, 1), len(tiers)) - 1]


def crossed_force_threshold(cfg: ZoneConfig, previous: int, current: int) -> bool:
    """Did the blob just shrink DOWN through one of the forced sizes?

    `previous <= 0` never counts: that is the first measurement of a fight, and
    arriving at a size is not the same as falling to it.
    """
    if previous <= 0:
        return False
    return any((previous > size) and (current <= size) for size in cfg.force_reaim_at_sizes)


def reaim_windows(cfg: ZoneConfig, blob_size: int) -> tuple[float, float]:
    """Commit window and recompute floor, in ms, for a blob of this size."""
    return (
        cfg.reaim_commit_ms * tier_for(cfg.reaim_commit_slowdown_tiers, blob_size),
        cfg.min_facing_recompute_ms * tier_for(cfg.reaim_floor_slowdown_tiers, blob_size),
    )


def should_reaim(zone: FightZone, cfg: ZoneConfig, inputs: "ZoneInputs") -> bool:
    """Has the fight moved enough, for long enough, to be worth re-forming?

    Measured against the SELECTED BLOB, recomputed exactly as anchoring does.
    Comparing an all-enemy centroid against a stored blob centroid compares two
    different quantities: with two mob groups they sit permanently hundreds of
    units apart, so the test fires forever and every firing re-clamps the anchor
    to wherever the leader is standing.
    """
    now_ms = inputs.now_ms
    if zone.last_facing_target is None:
        return False

    # Enemies that have already reached the contact point tell us nothing about
    # where to stand — they are where we expected them. Judging on the ones
    # still out there is what stops a charging melee mob from walking the
    # formation backwards as it closes.
    approaching = [
        position
        for position in inputs.enemy_positions
        if math.hypot(position[0] - zone.engagement_x, position[1] - zone.engagement_y) > cfg.contact_radius
    ]
    if not approaching:
        zone.reaim_pending_since_ms = 0
        zone.reaim_blob_size = 0
        return False

    # Counted on the still-approaching set rather than every enemy alive: that
    # set is what the re-aim maths is measured against, so it is the one whose
    # instability matters.
    blob = resolve_engagement_blob(cfg, inputs.party_xy, approaching)
    zone.reaim_blob_size = len(blob)
    commit_window, recompute_floor = reaim_windows(cfg, len(blob))
    zone.reaim_commit_window_ms = commit_window
    zone.reaim_floor_ms = recompute_floor

    # Measured before the geometry test, and deliberately not updated in the
    # no-approaching-enemies branch above: an empty approach set means the mob
    # closed to contact, not that it died, and treating that as a shrink would
    # spend the force on a pack that is already on top of the front line.
    forced = crossed_force_threshold(cfg, zone.last_blob_size, len(blob))
    zone.last_blob_size = len(blob)

    blob_centre = centroid(blob)
    if blob_centre is None:
        zone.reaim_pending_since_ms = 0
        return False

    # Ahead of the swing/drift test, not just the timers. Killing one of three
    # moves the blob centroid ~150u, which is real movement the lateral gate is
    # built to ignore — so waiting for geometry to argue for it defeats the
    # point of forcing.
    if forced:
        zone.reaim_pending_since_ms = 0
        zone.forced_reaim_count += 1
        return True

    engagement = clamp_toward(blob_centre, inputs.party_xy, cfg.max_anchor_offset_from_party)
    proposed = compute_axis(
        zone, cfg, inputs.party_xy, inputs.approach_xy, blob_centre, engagement, inputs.retreat_axis
    )
    swing = angle_difference(proposed, zone.facing)
    drift = math.hypot(
        blob_centre[0] - zone.last_facing_target[0],
        blob_centre[1] - zone.last_facing_target[1],
    )

    # Lateral component of the drift — how far the blob moved ACROSS the axis
    # rather than along it. Movement straight down the axis is a mob closing or
    # retreating, which never justifies turning the formation.
    lateral = drift * math.sin(min(swing, math.pi / 2.0))
    swung = swing >= cfg.reaim_angle_threshold and lateral >= cfg.reaim_min_lateral
    if not swung and drift < cfg.facing_rehome_distance:
        zone.reaim_pending_since_ms = 0
        return False

    if zone.reaim_pending_since_ms == 0:
        zone.reaim_pending_since_ms = now_ms
        return False
    if (now_ms - zone.reaim_pending_since_ms) < commit_window:
        return False
    # A floor, not a rejection: pending is deliberately left standing so the
    # re-aim fires the moment the floor expires rather than restarting the
    # confirmation from scratch.
    if (now_ms - zone.last_facing_ms) < recompute_floor:
        return False

    zone.reaim_pending_since_ms = 0
    return True


def ground_ceiling(cfg: ZoneConfig, inputs: "ZoneInputs") -> float:
    """How far back the party may be pulled, in route metres.

    The plotted route sets it, not a constant: backing up further than the way
    out actually runs walks the formation into the geometry the route already
    mapped. A margin is held back so the pin never lands exactly on the far end,
    where the next step would have nowhere to go.
    """
    if not inputs.retreat_path or inputs.retreat_distance <= 0.0:
        return 0.0
    return max(0.0, min(cfg.max_given_ground, inputs.retreat_distance - cfg.give_ground_margin))


def given_ground(zone: FightZone) -> float:
    return sum(math.hypot(x, y) for x, y in zone.retreat_steps)


def ground_offset(zone: FightZone) -> tuple[float, float]:
    """Latched displacement of the formation from its authored position."""
    x = sum(step[0] for step in zone.retreat_steps)
    y = sum(step[1] for step in zone.retreat_steps)
    if zone.advance > 0.0:
        x += math.cos(zone.facing) * zone.advance
        y += math.sin(zone.facing) * zone.advance
    return (x, y)


@dataclass(slots=True, frozen=True)
class TriggerRing:
    """An ellipse in the formation's local frame, all distances along facing."""

    centre: float
    fwd: float
    lat: float

    def tip(self) -> float:
        """Depth of the forward edge — where this ring trips."""
        return self.centre + self.fwd


def local_frame(
    point: tuple[float, float],
    anchor: tuple[float, float],
    facing: float,
) -> tuple[float, float]:
    """World point to (along-facing, across-facing), origin at the pin."""
    dx = point[0] - anchor[0]
    dy = point[1] - anchor[1]
    cos_f = math.cos(facing)
    sin_f = math.sin(facing)
    return ((dx * cos_f) + (dy * sin_f), (dy * cos_f) - (dx * sin_f))


def inside_ring(ring: TriggerRing, point: tuple[float, float], zone: FightZone) -> bool:
    if ring.fwd <= 0.0 or ring.lat <= 0.0:
        return False
    fwd, lat = local_frame(point, (zone.anchor_x, zone.anchor_y), zone.facing)
    return (((fwd - ring.centre) / ring.fwd) ** 2) + ((lat / ring.lat) ** 2) < 1.0


def blob_depth(zone: FightZone, cfg: ZoneConfig, inputs: "ZoneInputs") -> float | None:
    """How far in FRONT of the front line the enemy blob's centre sits.

    Negative means it has pushed past the pin and in among the formation. Kept
    as the readout the tab shows; the triggers themselves run on rings, which
    also read the lateral half this discards.
    """
    blob = centroid(resolve_engagement_blob(cfg, inputs.party_xy, inputs.enemy_positions))
    if blob is None:
        return None
    return local_frame(blob, (zone.anchor_x, zone.anchor_y), zone.facing)[0]


def overrun_depth(inputs: "ZoneInputs") -> float:
    """The no-cross depth, imposed FORWARD of the mid rank.

    Halfway between the front and mid ranks. A trigger at the mid rank itself
    fires only when the casters are already being walked through — too late by
    definition, since the whole point is that the blob's centre must never get
    there. Halfway sits behind honest front-line wrap (a pack mobbing the pins
    puts its centroid just behind them at worst), and one give_ground_step
    still clears it, so the trigger stays self-releasing.
    """
    return inputs.midline_depth * 0.5


def midline_ring(cfg: ZoneConfig, inputs: "ZoneInputs") -> TriggerRing:
    """Soft trip. Tip pinned to overrun_depth so the depth matches the flat
    plane this replaces and `lat` is the only new quantity."""
    return TriggerRing(-overrun_depth(inputs) - cfg.midline_ring_fwd, cfg.midline_ring_fwd, cfg.midline_ring_lat)


def backline_ring(cfg: ZoneConfig, inputs: "ZoneInputs") -> TriggerRing:
    """Panic ring, centred on the rear rank, tip held behind the midline's.

    The clamp is not cosmetic. backline_ring_fwd is a fixed 322 while the rank
    it sits on comes from the formation, so a compressed one puts the tip in
    FRONT of the midline trip — at a 310u back rank it lands at +12, ahead of
    the pin, and the emergency fires before the soft step ever gets a chance.
    Untouched on any formation deep enough to order itself: the default clears
    this by 138u against a 100u margin.
    """
    ring = TriggerRing(-inputs.backline_depth, cfg.backline_ring_fwd, cfg.backline_ring_lat)
    ceiling = midline_ring(cfg, inputs).tip() - cfg.ring_escalation_margin
    if ring.tip() <= ceiling:
        return ring
    return TriggerRing(ring.centre, max(0.0, ceiling - ring.centre), ring.lat)


def frontline_ring(cfg: ZoneConfig) -> TriggerRing:
    return TriggerRing(cfg.frontline_ring_centre, cfg.frontline_ring_fwd, cfg.frontline_ring_lat)


def blob_centre(cfg: ZoneConfig, inputs: "ZoneInputs") -> tuple[float, float] | None:
    return centroid(resolve_engagement_blob(cfg, inputs.party_xy, inputs.enemy_positions))


def overrun(zone: FightZone, cfg: ZoneConfig, inputs: "ZoneInputs") -> bool:
    """The blob's centre is inside the midline ring.

    Geometric rather than a health reading, and self-releasing because of it:
    backing up moves the ring away from the mob, so the condition clears itself
    once enough ground has been given and not a step sooner. A health threshold
    has no such feedback and simply ratchets.
    """
    blob = blob_centre(cfg, inputs)
    return blob is not None and inside_ring(midline_ring(cfg, inputs), blob, zone)


def backline_breached(zone: FightZone, cfg: ZoneConfig, inputs: "ZoneInputs") -> bool:
    """The blob's centre of mass has reached the rear rank. Outranks every other
    reading and does not wait out the recover dwell."""
    blob = blob_centre(cfg, inputs)
    return blob is not None and inside_ring(backline_ring(cfg, inputs), blob, zone)


def frontline_reached(zone: FightZone, cfg: ZoneConfig, inputs: "ZoneInputs") -> bool:
    """The blob's centre of mass has arrived inside the frontline ring.

    Closing stops here, not when the ring empties. All three rings now read the
    same centroid, so a single straggler, a puller, or the one enemy that ran
    ahead no longer pins the party where it stands while the pack it is supposed
    to be fighting sits out of reach.

    The cost is deliberate and worth stating: the front rank is already trading
    blows before the centroid arrives, because half a pack straddling the ring
    averages out beyond it. Advancing into a fight already joined is the accepted
    trade for not stalling on one body in the hole.
    """
    blob = blob_centre(cfg, inputs)
    return blob is not None and inside_ring(frontline_ring(cfg), blob, zone)


def retreat_step_vector(inputs: "ZoneInputs", step: float) -> tuple[float, float] | None:
    """One step along the escape route's local heading, where the party is now.

    Only the STEP is read off the route, never the whole displacement. The route
    is replotted every second from a party centre that is itself moving, so its
    bearing wobbles by a ray step or two even when nothing has changed; measuring
    the full withdrawal against it each time multiplied that wobble by how far
    the party had already withdrawn, and walked the formation around all fight.
    Stepping instead means a replot can only ever affect the next step.
    """
    if step <= 0.0 or not inputs.retreat_path:
        return None
    origin = inputs.retreat_path[0]
    ahead = sample_at(inputs.retreat_path, step)
    dx = ahead[0] - origin[0]
    dy = ahead[1] - origin[1]
    span = math.hypot(dx, dy)
    if span < 0.001:
        return None
    # Normalised to exactly `step`: sampling across a bend returns a chord, and
    # letting that shorten the move would make cornering quietly lose ground.
    return (dx * (step / span), dy * (step / span))


def ground_dwell_ms(cfg: ZoneConfig, inputs: "ZoneInputs", tiers: tuple[float, ...]) -> int:
    """Dwell for the size of the blob being measured, off the authored table."""
    blob = resolve_engagement_blob(cfg, inputs.party_xy, inputs.enemy_positions)
    return int(tier_for(tiers, len(blob)))


def adjust_ground(zone: FightZone, cfg: ZoneConfig, inputs: "ZoneInputs") -> None:
    """Back off, close, or hold — one deliberate move, then sit.

    Three rings decide everything, tested against the blob in the formation's
    own frame. PURELY GEOMETRIC — health deliberately has no vote. The readings
    are not yet trusted, and a wrong one here either routs a winning party or
    pins a losing one; they are published for the tab so they can be watched
    until they are.

    RETREAT on the midline ring, whose forward tip sits ahead of the mid rank,
    and again — harder, and without waiting out the dwell — on the backline
    ring centred on the rear rank. The two are ordered by construction: the
    midline tip is the shallower of the pair, so the soft step always gets its
    chance before the emergency does.

    CLOSE while the blob's centre of mass is still OUTSIDE the frontline ring,
    one step per dwell. Self-limiting: every step drags the ring forward onto the
    mob, so closing stops as soon as the centre of the pack is in reach.

    HOLD otherwise, and always for the dwell after any move — one deliberate
    move, then long enough for heals to land and the mob to re-form in front,
    rather than a continuous slide. Retreat dwells come off the authored
    per-size table, since the tail of a fight is the twitchiest reading and
    should give ground most rarely; advance is a flat cadence at any blob size.

    The formation TRANSLATES and never rotates, so the enemies stay squarely in
    front however far it moves; facing is decided elsewhere, on the blob.
    """
    breached = backline_breached(zone, cfg, inputs)
    zone.breached = breached
    if not breached and inputs.now_ms < zone.hold_until_ms:
        return

    if breached or overrun(zone, cfg, inputs):
        ceiling = ground_ceiling(cfg, inputs)
        step = min(cfg.give_ground_step, max(0.0, ceiling - given_ground(zone)))
        vector = retreat_step_vector(inputs, step)
        if vector is not None:
            if zone.advance > 0.0:
                zone.advance = max(0.0, zone.advance - cfg.give_ground_step)
            else:
                zone.retreat_steps.append(vector)
            zone.hold_until_ms = inputs.now_ms + (
                cfg.breach_hold_ms if breached else ground_dwell_ms(cfg, inputs, cfg.recover_hold_tiers_ms)
            )
    elif not frontline_reached(zone, cfg, inputs):
        # Give back the way out first, retracing it exactly, before pushing past
        # the authored position. Popping the stack is what stops a dogleg
        # withdrawal being unwound through the corner it went round.
        if zone.retreat_steps:
            zone.retreat_steps.pop()
        else:
            zone.advance += cfg.give_ground_step
        zone.hold_until_ms = inputs.now_ms + cfg.advance_hold_ms

    zone.giving_ground = bool(zone.retreat_steps)
    zone.closing = zone.advance > 0.0
    # Unconditional, including when the offset is back to zero. Skipping that
    # case left the pin wherever the last step had put it, so the formation
    # never actually returned to its authored position — it just stopped
    # being told to move.
    zone.anchor_x, zone.anchor_y = positioned_anchor(zone, cfg)


def positioned_anchor(zone: FightZone, cfg: ZoneConfig) -> tuple[float, float]:
    """Authored pin plus whatever ground has been given or taken."""
    base = apply_standoff((zone.engagement_x, zone.engagement_y), zone.facing, cfg.engagement_standoff)
    offset_x, offset_y = ground_offset(zone)
    return (base[0] + offset_x, base[1] + offset_y)


def latch_facing(
    zone: FightZone,
    engagement_xy: tuple[float, float],
    approach_xy: tuple[float, float] | None,
    leader_xy: tuple[float, float],
    enemy_positions: list[tuple[float, float]],
    now_ms: int,
) -> None:
    zone.facing = compute_zone_facing(zone, engagement_xy, approach_xy, leader_xy, enemy_positions)
    zone.last_facing_target = centroid(enemy_positions)
    zone.last_facing_ms = now_ms


@dataclass(slots=True)
class ZoneInputs:
    leader_xy: tuple[float, float]
    enemy_positions: list[tuple[float, float]]
    party_in_aggro: bool
    leader_local_aggro: bool
    loot_pending: bool
    members_in_position: bool
    now_ms: int
    # Centre of mass of the party. The blob axis is measured from here.
    party_xy: tuple[float, float] = (0.0, 0.0)
    # Where the party walked in from. None when it sits too close to say.
    approach_xy: tuple[float, float] | None = None
    # Bearing of the plotted escape route, pointing OUTWARD from the party.
    # The formation's rear is aimed along it so backing up follows the way out.
    retreat_axis: float | None = None
    # The escape route as a polyline from the party outward, and its length.
    # give_ground walks this, so a backtrack round a corner is followed rather
    # than cut across.
    retreat_path: list[tuple[float, float]] = field(default_factory=list)
    retreat_distance: float = 0.0
    # Depth of the formation's middle rank behind the front line, positive.
    # The midline ring's tip is imposed at overrun_depth ahead of it. Read from
    # the loaded formation so an authored one is judged by its own shape.
    midline_depth: float = 320.0
    # Depth of the rear rank, where the panic ring is centred. Same reasoning.
    backline_depth: float = 620.0


def enter_state(zone: FightZone, state: ZoneState, now_ms: int) -> None:
    if zone.state == state:
        return
    zone.state = state
    zone.entered_state_ms = now_ms


def tick_zone(zone: FightZone, cfg: ZoneConfig, inputs: ZoneInputs) -> FightZone:
    now = inputs.now_ms

    if zone.state == ZoneState.TRAVELING:
        if inputs.party_in_aggro:
            zone.radius = cfg.engage_radius
            zone.last_facing_target = None
            zone.last_blob_size = 0
            # A new fight starts at the authored position. The abandon-and-
            # redrop below deliberately does NOT reset this: that path is the
            # same fight continuing somewhere else, and ground given to it
            # still counts.
            zone.retreat_steps.clear()
            zone.advance = 0.0
            zone.hold_until_ms = 0
            zone.giving_ground = False
            zone.closing = False
            zone.anchor_x, zone.anchor_y = anchor_and_facing(
                zone,
                cfg,
                inputs.leader_xy,
                inputs.party_xy,
                inputs.approach_xy,
                inputs.enemy_positions,
                now,
                inputs.retreat_axis,
            )
            enter_state(zone, ZoneState.ENGAGING, now)
        return zone

    leader_distance = math.hypot(
        inputs.leader_xy[0] - zone.anchor_x,
        inputs.leader_xy[1] - zone.anchor_y,
    )

    # Leader has left the pin behind. Still fighting means the engagement moved
    # with them, so re-drop the pin rather than falling back to plain follow —
    # breaking off mid-fight drags an aggro train.
    if leader_distance > cfg.abandon_distance:
        if inputs.party_in_aggro and inputs.leader_local_aggro:
            zone.last_facing_target = None
            zone.last_blob_size = 0
            zone.anchor_x, zone.anchor_y = anchor_and_facing(
                zone,
                cfg,
                inputs.leader_xy,
                inputs.party_xy,
                inputs.approach_xy,
                inputs.enemy_positions,
                now,
                inputs.retreat_axis,
            )
            enter_state(zone, ZoneState.ENGAGING, now)
            return zone
        enter_state(zone, ZoneState.TRAVELING, now)
        return zone

    if zone.state == ZoneState.ENGAGING:
        if should_reaim(zone, cfg, inputs):
            zone.anchor_x, zone.anchor_y = anchor_and_facing(
                zone,
                cfg,
                inputs.leader_xy,
                inputs.party_xy,
                inputs.approach_xy,
                inputs.enemy_positions,
                now,
                inputs.retreat_axis,
            )
        adjust_ground(zone, cfg, inputs)
        if not inputs.party_in_aggro:
            enter_state(zone, ZoneState.CLEARING, now)
            return zone
        if inputs.members_in_position or (now - zone.entered_state_ms) >= cfg.engage_timeout_ms:
            enter_state(zone, ZoneState.HOLDING, now)
        return zone

    if zone.state == ZoneState.HOLDING:
        if should_reaim(zone, cfg, inputs):
            zone.anchor_x, zone.anchor_y = anchor_and_facing(
                zone,
                cfg,
                inputs.leader_xy,
                inputs.party_xy,
                inputs.approach_xy,
                inputs.enemy_positions,
                now,
                inputs.retreat_axis,
            )
        adjust_ground(zone, cfg, inputs)
        if not inputs.party_in_aggro:
            enter_state(zone, ZoneState.CLEARING, now)
        return zone

    # CLEARING: hold the pin through looting so nobody wanders off mid-pickup.
    if inputs.party_in_aggro:
        enter_state(zone, ZoneState.ENGAGING, now)
        return zone
    if not inputs.loot_pending:
        enter_state(zone, ZoneState.TRAVELING, now)
    return zone
