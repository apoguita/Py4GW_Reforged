"""Generated static interaction catalog partition. Do not edit rows in isolation."""

from __future__ import annotations

from .schema import IdentityRow
from .schema import OccurrenceRow

PARTITION = "prophecies_thirsty_river"

IDENTITIES: tuple[IdentityRow, ...] = (
    (
        'prophecies.thirsty_river.identity.ghostly_hero',
        'npc',
        ('Ghostly Hero',),
        (12693, 37925, 43966, 16551),
        None,
        (1785,),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-20261107-THIRSTY-GHOSTLY-HERO'),
                (
                    'scope',
                    'User supplied exact automation identity and confirmed it inside the mission; capture XY '
                    'explicitly excluded.',
                ),
            ),
        ),
    ),
    (
        'prophecies.thirsty_river.identity.king_khimaar',
        'npc',
        ('King Khimaar',),
        (12687, 39816, 47826, 12285),
        None,
        (2882,),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-20261107-THIRSTY-KING-KHIMAAR'),
                (
                    'scope',
                    'User requests preserving the King from step 9 onward. Exact automation identity ' 'supplied.',
                ),
            ),
        ),
    ),
)

OCCURRENCES: tuple[OccurrenceRow, ...] = (
    (
        'prophecies.npc.ghostly_hero.thirsty_river.start',
        'prophecies.thirsty_river.identity.ghostly_hero',
        117,
        'Thirsty River',
        (8945.0, -2457.0),
        (8865.0, -2420.0),
        ('NPC-20260829-101658-825', 'USER-20261107-THIRSTY-GHOSTLY-HERO:start'),
        'candidate',
        (
            (
                ('source_type', 'existing_capture_occurrence'),
                ('capture_id', 'NPC-20260829-101658-825'),
                (
                    'scope',
                    'Existing authoritative mission geometry preserved; recovery follows the uniquely resolved '
                    'live actor.',
                ),
            ),
        ),
    ),
    (
        'prophecies.npc.ghostly_hero.thirsty_river.follow_recovery',
        'prophecies.thirsty_river.identity.ghostly_hero',
        117,
        'Thirsty River',
        (6484.0, -9438.0),
        (6403.19, -9454.74),
        ('NPC-20260829-131246-453', 'USER-20261107-THIRSTY-GHOSTLY-HERO:follow_recovery'),
        'candidate',
        (
            (
                ('source_type', 'existing_capture_occurrence'),
                ('capture_id', 'NPC-20260829-131246-453'),
                (
                    'scope',
                    'Existing authoritative mission geometry preserved; recovery follows the uniquely resolved '
                    'live actor.',
                ),
            ),
        ),
    ),
    (
        'prophecies.npc.king_khimaar.thirsty_river.final_arena',
        'prophecies.thirsty_river.identity.king_khimaar',
        117,
        'Thirsty River',
        (-697.83, -8929.88),
        None,
        ('USER-20261107-THIRSTY-KING-KHIMAAR',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-20261107-THIRSTY-KING-KHIMAAR'),
                (
                    'scope',
                    'Stationary ally-protection anchor; player XY was diagnostic, not an approach ' 'instruction.',
                ),
            ),
        ),
    ),
)
