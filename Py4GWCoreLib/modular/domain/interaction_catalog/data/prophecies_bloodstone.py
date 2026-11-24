"""Generated static interaction catalog partition. Do not edit rows in isolation."""

from __future__ import annotations

from .schema import IdentityRow
from .schema import OccurrenceRow

PARTITION = "prophecies_bloodstone"

IDENTITIES: tuple[IdentityRow, ...] = (
    (
        'prophecies.bloodstone.identity.vine_seed',
        'item',
        ('Vine Seed',),
        (9568, 44071, 59375, 7490),
        None,
        (2579,),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-BLOODSTONE-SEED-1-20261102'),
                (
                    'scope',
                    'Three matching encoded seed captures; paired ground/held dumps prove model2579 and Bundle '
                    'type.',
                ),
            ),
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-WILDS-VINE-SEED-20261122'),
                (
                    'scope',
                    'The Wilds ground and held-slot dumps match the reviewed Vine Seed automation identity and '
                    'held model 2579.',
                ),
            ),
        ),
    ),
)

OCCURRENCES: tuple[OccurrenceRow, ...] = (
    (
        'prophecies.item.vine_seed.bloodstone_fen.11391_-967',
        'prophecies.bloodstone.identity.vine_seed',
        10,
        'Bloodstone Fen',
        (11391.08, -967.29),
        (12106.22, -1229.55),
        ('USER-BLOODSTONE-SEED-1-20261102',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-BLOODSTONE-SEED-1-20261102'),
                (
                    'scope',
                    'Dropped Vine Seed matched to held item1120; target is occurrence evidence, not a mandatory '
                    'approach.',
                ),
            ),
        ),
    ),
    (
        'prophecies.item.vine_seed.the_wilds.-1590_-12456',
        'prophecies.bloodstone.identity.vine_seed',
        11,
        'The Wilds',
        (-1590.08, -12455.55),
        (-1626.08, -12713.06),
        ('USER-WILDS-VINE-SEED-20261122',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-WILDS-VINE-SEED-20261122'),
                (
                    'scope',
                    'Captured as an item on map 11; ground runtime agent 41/item 10 is transient. Held-slot '
                    'evidence proves model 2579 and exact ground-to-held model continuity.',
                ),
            ),
        ),
    ),
)
