"""Generated static interaction catalog partition. Do not edit rows in isolation."""

from __future__ import annotations

from .schema import IdentityRow
from .schema import OccurrenceRow

PARTITION = "mission_runner_canonical_cleanup"

IDENTITIES: tuple[IdentityRow, ...] = (
    (
        'prophecies.npc.keep_gate_guard',
        'npc',
        ("Lion's Arch Keep gate guard",),
        (33026, 26364, 48463, 35615, 5008),
        None,
        (),
        'candidate',
        (
            (
                ('source_type', 'user_route_capture'),
                ('capture_id', 'ROUTE-20261006-200438-381:points-0-16'),
                ('scope', 'Exact captured encoded identity and occurrence geometry only.'),
            ),
        ),
    ),
    (
        'cantha.npc.dinja',
        'npc',
        ('Dinja',),
        (33025, 19261, 40728, 26928),
        None,
        (),
        'candidate',
        (
            (
                ('source_type', 'user_route_capture'),
                ('capture_id', 'ROUTE-20261024-125656-213'),
                ('scope', 'Exact captured encoded identity and occurrence geometry only.'),
            ),
        ),
    ),
    (
        'prophecies.npc.livia',
        'npc',
        ('Livia',),
        (33025, 30640),
        None,
        (),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('scope', 'Exact captured encoded identity and occurrence geometry only.'),
            ),
        ),
    ),
    (
        'prophecies.npc.jiaju_tai',
        'npc',
        ('Jiaju Tai',),
        (12526, 40581, 59878, 12247),
        None,
        (),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('scope', 'Exact captured encoded identity and occurrence geometry only.'),
            ),
        ),
    ),
)

OCCURRENCES: tuple[OccurrenceRow, ...] = (
    (
        'prophecies.npc.keep_gate_guard.lions_arch.7611_10627',
        'prophecies.npc.keep_gate_guard',
        55,
        "Lion's Arch",
        (7611.0, 10627.0),
        (7570.36, 10617.87),
        ('ROUTE-20261006-200438-381:points-0-16',),
        'candidate',
        ((('source_type', 'registered_mission_occurrence'),),),
    ),
    (
        'cantha.npc.dinja.outpost_493.-2367_16796',
        'cantha.npc.dinja',
        493,
        'Outpost 493',
        (-2367.0, 16796.0),
        (-2431.61, 16841.15),
        ('ROUTE-20261024-125656-213', 'USER-JUSTICE-NPC-CAPTURES', 'USER-ZENMAI-NPC-CAPTURES'),
        'candidate',
        ((('source_type', 'registered_mission_occurrence'),),),
    ),
    (
        'prophecies.npc.livia.asuran_lab.-12855_-7768',
        'prophecies.npc.livia',
        839,
        'Asuran Lab',
        (-12855.0, -7768.0),
        (-12681.35, -7815.4),
        ('codex-clipboard-47acf9f1-e999-41c3-a49d-3cd1bd79fda3.png', 'ROUTE-20261007-173349-746:point-247'),
        'candidate',
        ((('source_type', 'registered_mission_occurrence'),),),
    ),
    (
        'prophecies.npc.jiaju_tai.lions_arch.1444_1925',
        'prophecies.npc.jiaju_tai',
        55,
        "Lion's Arch",
        (1444.0, 1925.0),
        (1494.86, 2011.1),
        (
            'codex-clipboard-e378cd5e-1e9b-43d5-97a7-64f290d65e01.png',
            'codex-clipboard-5c8e7347-2091-45f1-97b6-48917a9b7c96.png',
            'codex-clipboard-e73cf28d-87a7-403b-bf84-20fcc9839e74.png',
            'ROUTE-20261007-170037-712:points-0-17',
        ),
        'candidate',
        ((('source_type', 'registered_mission_occurrence'),),),
    ),
)
