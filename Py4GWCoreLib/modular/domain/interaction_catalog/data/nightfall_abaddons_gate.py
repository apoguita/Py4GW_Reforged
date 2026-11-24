"""Generated static interaction catalog partition. Do not edit rows in isolation."""

from __future__ import annotations

from .schema import IdentityRow
from .schema import OccurrenceRow

PARTITION = "nightfall_abaddons_gate"

IDENTITIES: tuple[IdentityRow, ...] = (
    (
        'nightfall.npc.keeper_sharissh.encoded',
        'npc',
        ('Keeper Sharissh',),
        None,
        ('npc', 'KEEPER_SHARISSH', 0),
        (5053,),
        'reviewed',
        (
            (
                ('source_type', 'user_supplied_entity_capture'),
                ('source_sha256', '997B0436B772F94E9D4EB5B65EBC3898AFBF2BCDB41028676A39493CF6518859'),
            ),
        ),
    ),
    (
        'nightfall.npc.keeper_of_secrets.encoded',
        'npc',
        ('Keeper of Secrets',),
        None,
        ('npc', 'KEEPER_OF_SECRETS', 0),
        (5053,),
        'reviewed',
        (
            (
                ('source_type', 'user_supplied_entity_capture'),
                ('source_sha256', '5B64E31D93D18F28BD33412B47A4390B885B8562781D6EEE957D74CB101D55D1'),
            ),
        ),
    ),
)

OCCURRENCES: tuple[OccurrenceRow, ...] = (
    (
        'nightfall.npc.keeper_sharissh.496',
        'nightfall.npc.keeper_sharissh.encoded',
        496,
        'Abaddons Gate',
        (15192.0, -3817.0),
        (15224.97, -3876.42),
        ('USER-20261104-KEEPER_SHARISSH',),
        'reviewed',
        (
            (
                ('source_type', 'user_supplied_entity_capture'),
                ('source_sha256', '997B0436B772F94E9D4EB5B65EBC3898AFBF2BCDB41028676A39493CF6518859'),
            ),
        ),
    ),
    (
        'nightfall.npc.keeper_of_secrets.503',
        'nightfall.npc.keeper_of_secrets.encoded',
        503,
        'Throne of Secrets',
        (-17059.0, 5821.0),
        (-17055.79, 5897.63),
        ('USER-20261104-KEEPER_OF_SECRETS',),
        'reviewed',
        (
            (
                ('source_type', 'user_supplied_entity_capture'),
                ('source_sha256', '5B64E31D93D18F28BD33412B47A4390B885B8562781D6EEE957D74CB101D55D1'),
            ),
        ),
    ),
)
