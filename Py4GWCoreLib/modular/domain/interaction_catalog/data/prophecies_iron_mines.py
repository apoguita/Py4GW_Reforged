"""Generated static interaction catalog partition. Do not edit rows in isolation."""

from __future__ import annotations

from .schema import IdentityRow
from .schema import OccurrenceRow

PARTITION = "prophecies_iron_mines"

IDENTITIES: tuple[IdentityRow, ...] = (
    (
        'prophecies.iron_mines.identity.seer',
        'npc',
        ('Ancient Seer',),
        (15149, 46998, 52528, 25810),
        None,
        (),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'user-capture-ancient-seer-return-20261015'),
                (
                    'scope',
                    'Retained source capture referenced by the admitted iron_mines_ryder_pilot occurrence '
                    'inventory and 2026-10-15 work order; no new capture is claimed.',
                ),
            ),
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'NPC-20260807-163615-435'),
                (
                    'scope',
                    'Retained source capture referenced by the admitted iron_mines_ryder_pilot occurrence '
                    'inventory and 2026-10-15 work order; no new capture is claimed.',
                ),
            ),
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'NPC-20260807-163623-309'),
                (
                    'scope',
                    'Retained source capture referenced by the admitted iron_mines_ryder_pilot occurrence '
                    'inventory and 2026-10-15 work order; no new capture is claimed.',
                ),
            ),
        ),
    ),
    (
        'prophecies.iron_mines.identity.ryder',
        'npc',
        ('Shining Blade Scout Ryder',),
        (15114, 64241, 35316, 546),
        None,
        (),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'user-capture-shining-blade-scout-ryder-20261015'),
                (
                    'scope',
                    'Retained source capture referenced by the admitted iron_mines_ryder_pilot occurrence '
                    'inventory and 2026-10-15 work order; no new capture is claimed.',
                ),
            ),
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'iron-mines-route-marker-scout-ryder-safe-player'),
                (
                    'scope',
                    'Retained source capture referenced by the admitted iron_mines_ryder_pilot occurrence '
                    'inventory and 2026-10-15 work order; no new capture is claimed.',
                ),
            ),
        ),
    ),
)

OCCURRENCES: tuple[OccurrenceRow, ...] = (
    (
        'prophecies.npc.ancient_seer.iron_mines.-9232_26062',
        'prophecies.iron_mines.identity.seer',
        24,
        'Iron Mines of Moladune',
        (-9232.0, 26062.0),
        (-9126.07, 26083.33),
        ('user-capture-ancient-seer-return-20261015', 'NPC-20260807-163615-435', 'NPC-20260807-163623-309'),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'user-capture-ancient-seer-return-20261015'),
                (
                    'scope',
                    'Retained source capture referenced by the admitted iron_mines_ryder_pilot occurrence '
                    'inventory and 2026-10-15 work order; no new capture is claimed.',
                ),
            ),
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'NPC-20260807-163615-435'),
                (
                    'scope',
                    'Retained source capture referenced by the admitted iron_mines_ryder_pilot occurrence '
                    'inventory and 2026-10-15 work order; no new capture is claimed.',
                ),
            ),
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'NPC-20260807-163623-309'),
                (
                    'scope',
                    'Retained source capture referenced by the admitted iron_mines_ryder_pilot occurrence '
                    'inventory and 2026-10-15 work order; no new capture is claimed.',
                ),
            ),
        ),
    ),
    (
        'prophecies.npc.scout_ryder.iron_mines.-1956_-3113',
        'prophecies.iron_mines.identity.ryder',
        24,
        'Iron Mines of Moladune',
        (-1956.0, -3113.0),
        (-1944.79, -3125.46),
        ('user-capture-shining-blade-scout-ryder-20261015', 'iron-mines-route-marker-scout-ryder-safe-player'),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'user-capture-shining-blade-scout-ryder-20261015'),
                (
                    'scope',
                    'Retained source capture referenced by the admitted iron_mines_ryder_pilot occurrence '
                    'inventory and 2026-10-15 work order; no new capture is claimed.',
                ),
            ),
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'iron-mines-route-marker-scout-ryder-safe-player'),
                (
                    'scope',
                    'Retained source capture referenced by the admitted iron_mines_ryder_pilot occurrence '
                    'inventory and 2026-10-15 work order; no new capture is claimed.',
                ),
            ),
        ),
    ),
)
