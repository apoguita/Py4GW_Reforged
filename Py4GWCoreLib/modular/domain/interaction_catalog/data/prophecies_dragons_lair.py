"""Generated static interaction catalog partition. Do not edit rows in isolation."""

from __future__ import annotations

from .schema import IdentityRow
from .schema import OccurrenceRow

PARTITION = "prophecies_dragons_lair"

IDENTITIES: tuple[IdentityRow, ...] = (
    (
        'prophecies.dragons_lair.identity.forgotten_gate_keeper',
        'npc',
        ('Forgotten Gate Keeper',),
        (12737, 61780, 53579, 13741),
        None,
        (1877,),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-20261107-DRAGONS-LAIR-GATEKEEPER'),
                (
                    'scope',
                    'User confirms capture inside mission; outpost label inaccurate. Runtime agent 20 is '
                    'diagnostic only.',
                ),
            ),
        ),
    ),
)

OCCURRENCES: tuple[OccurrenceRow, ...] = (
    (
        'prophecies.npc.forgotten_gate_keeper.dragons_lair.first_portal',
        'prophecies.dragons_lair.identity.forgotten_gate_keeper',
        120,
        "The Dragon's Lair",
        (-13467.0, 3793.0),
        (-13405.51, 3819.72),
        ('USER-20261107-DRAGONS-LAIR-GATEKEEPER',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-20261107-DRAGONS-LAIR-GATEKEEPER'),
                (
                    'scope',
                    'User confirms capture inside mission; outpost label inaccurate. Runtime agent 20 is '
                    'diagnostic only.',
                ),
            ),
        ),
    ),
)
