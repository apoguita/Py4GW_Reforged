"""Generated static interaction catalog partition. Do not edit rows in isolation."""

from __future__ import annotations

from .schema import IdentityRow
from .schema import OccurrenceRow

PARTITION = "eotn_tarnished_coast"

IDENTITIES: tuple[IdentityRow, ...] = (
    (
        'eotn.enemy.alpha_tyrannus',
        'npc',
        ('Alpha Tyrannus',),
        (33026, 27702, 58334, 37294, 10010),
        None,
        (9920,),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'user-20261120-norn-catering-alpha-tyrannus'),
                ('raw_units', [2, 129, 54, 108, 222, 227, 174, 145, 26, 39, 0, 0]),
                ('note', 'User explicitly identified Alpha as moving; the captured XY is encounter context only.'),
            ),
        ),
    ),
)

OCCURRENCES: tuple[OccurrenceRow, ...] = (
    (
        'eotn.enemy.alpha_tyrannus.alcazia_tangle.norn_catering',
        'eotn.enemy.alpha_tyrannus',
        572,
        'Alcazia Tangle',
        (-10578.48, 1464.91),
        None,
        ('user-20261120-norn-catering-alpha-tyrannus',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'user-20261120-norn-catering-alpha-tyrannus'),
                ('geometry_status', 'moving_actor_diagnostic_context_only'),
                ('consumer_fields', ['identity.encoded_name_runtime']),
            ),
        ),
    ),
)
