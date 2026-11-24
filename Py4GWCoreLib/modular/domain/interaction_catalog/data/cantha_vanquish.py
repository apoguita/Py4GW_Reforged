"""Generated static interaction catalog partition. Do not edit rows in isolation."""

from __future__ import annotations

from .schema import IdentityRow
from .schema import OccurrenceRow

PARTITION = "cantha_vanquish"

IDENTITIES: tuple[IdentityRow, ...] = (
    (
        'cantha.npc.luxon_priest.enc_3f69_baa2_f307_2cc1',
        'npc',
        ('Luxon Priest',),
        (16233, 47778, 62215, 11457),
        None,
        (3692,),
        'reviewed',
        ((('source_type', 'archived_chat_recovery'), ('locator', 'structured_capture_union/26')),),
    ),
    (
        'cantha.npc.kurzick_priest',
        'npc',
        ('Kurzick Priest',),
        (16024, 43576, 1117),
        None,
        (3477,),
        'candidate',
        (
            (
                ('source_type', 'user_entity_capture'),
                ('source', 'Codex chat capture'),
                ('locator', 'Morostav Trail priest capture 2026-11-08'),
            ),
            (
                ('source_type', 'user_entity_capture'),
                ('source', 'Codex chat capture'),
                ('locator', 'Drazach priest capture 2026-11-08'),
            ),
            (
                ('source_type', 'user_entity_capture'),
                ('source', 'Codex chat capture'),
                ('locator', 'Arborstone priest capture 2026-11-03'),
            ),
        ),
    ),
)

OCCURRENCES: tuple[OccurrenceRow, ...] = (
    (
        'cantha.npc.luxon_priest.enc_3f69_baa2_f307_2cc1.maishang_hills.14126_-10653',
        'cantha.npc.luxon_priest.enc_3f69_baa2_f307_2cc1',
        199,
        'Maishang Hills',
        (14126.0, -10653.0),
        (13999.69, -10656.31),
        (),
        'reviewed',
        ((('source_type', 'archived_chat_recovery'), ('locator', 'structured_capture_union/26')),),
    ),
    (
        'cantha.npc.luxon_priest.enc_3f69_baa2_f307_2cc1.gyala_hatchery_explorable_area.7631_-19239',
        'cantha.npc.luxon_priest.enc_3f69_baa2_f307_2cc1',
        144,
        'Gyala Hatchery (explorable area)',
        (7631.0, -19239.0),
        (7707.69, -19226.34),
        (),
        'reviewed',
        ((('source_type', 'archived_chat_recovery'), ('locator', 'structured_capture_union/144')),),
    ),
    (
        'cantha.npc.kurzick_priest.morostav_trail.22109_12076',
        'cantha.npc.kurzick_priest',
        205,
        'Morostav Trail',
        (22109.0, 12076.0),
        (22145.03, 12141.94),
        (),
        'candidate',
        (
            (
                ('source_type', 'user_entity_capture'),
                ('source', 'Codex chat capture'),
                ('locator', 'Morostav Trail priest capture 2026-11-08'),
            ),
        ),
    ),
    (
        'cantha.npc.kurzick_priest.drazach_thicket.-5592_-16263',
        'cantha.npc.kurzick_priest',
        195,
        'Drazach Thicket',
        (-5592.0, -16263.0),
        (-5575.13, -16209.33),
        (),
        'candidate',
        (
            (
                ('source_type', 'user_entity_capture'),
                ('source', 'Codex chat capture'),
                ('locator', 'Drazach priest capture 2026-11-08'),
            ),
        ),
    ),
    (
        'cantha.npc.kurzick_priest.arborstone.10476_-19572',
        'cantha.npc.kurzick_priest',
        244,
        'Arborstone (explorable area)',
        (10476.0, -19572.0),
        (10414.26, -19583.35),
        (),
        'candidate',
        (
            (
                ('source_type', 'user_entity_capture'),
                ('source', 'Codex chat capture'),
                ('locator', 'Arborstone priest capture 2026-11-03'),
            ),
        ),
    ),
    (
        'cantha.npc.luxon_priest.boreas_seabed.13935_-9979',
        'cantha.npc.luxon_priest.enc_3f69_baa2_f307_2cc1',
        247,
        'Boreas Seabed (explorable area)',
        (13935.0, -9979.0),
        (13869.13, -10006.24),
        (),
        'candidate',
        (
            (
                ('source_type', 'user_entity_capture'),
                ('source', 'Codex chat capture'),
                ('locator', 'Boreas priest capture 2026-11-03'),
            ),
        ),
    ),
    (
        'cantha.npc.luxon_priest.enc_3f69_baa2_f307_2cc1.rheas_crater.13324_-1361',
        'cantha.npc.luxon_priest.enc_3f69_baa2_f307_2cc1',
        202,
        "Rhea's Crater",
        (13323.87, -1361.46),
        (13319.83, -1410.99),
        ('USER-20261121-RHEAS-CRATER-PRIEST-2',),
        'candidate',
        (
            (
                ('source_type', 'user_entity_capture'),
                ('source', 'Codex chat capture'),
                ('locator', "Rhea's Crater Luxon Priest capture 2026-11-21"),
            ),
        ),
    ),
    (
        'cantha.npc.kurzick_priest.mourning_veil_falls.-16475_-6496',
        'cantha.npc.kurzick_priest',
        209,
        'Mourning Veil Falls',
        (-16475.0, -6496.0),
        (-16516.58, -6547.67),
        (),
        'candidate',
        (
            (
                ('source_type', 'user_entity_capture'),
                ('source', 'Codex chat capture'),
                ('locator', 'Mourning Veil Falls priest capture 2026-11-11'),
            ),
        ),
    ),
)
