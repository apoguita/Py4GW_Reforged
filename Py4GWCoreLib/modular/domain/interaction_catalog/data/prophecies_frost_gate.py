"""Generated static interaction catalog partition. Do not edit rows in isolation."""

from __future__ import annotations

from .schema import IdentityRow
from .schema import OccurrenceRow

PARTITION = "prophecies_frost_gate"

IDENTITIES: tuple[IdentityRow, ...] = (
    (
        'prophecies.frost_gate.identity.rornak',
        'npc',
        ('Rornak Stonesledge',),
        (14964, 36986, 26527),
        None,
        (1562,),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-FROST-GATE-20261105-RORNAK'),
                ('scope', 'Exact user supplied automation identity; runtime agent ID excluded.'),
            ),
        ),
    ),
    (
        'prophecies.frost_gate.identity.firing_lever',
        'gadget',
        ('Firing lever',),
        (8504, 52207, 54270, 4271),
        None,
        (),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-FROST-GATE-20261105-FIRING_LEVER'),
                ('scope', 'Exact user supplied automation identity; runtime agent ID excluded.'),
            ),
        ),
    ),
    (
        'prophecies.frost_gate.identity.chest',
        'gadget',
        ('Chest',),
        None,
        ('gadget', 'CHEST', 0),
        (),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-FROST-GATE-20261105-CHEST'),
                ('scope', 'Exact user supplied automation identity; runtime agent ID excluded.'),
            ),
        ),
    ),
    (
        'prophecies.frost_gate.identity.plans',
        'item',
        ('Secret Siege Weapon Plans',),
        (9608, 35136, 18998),
        None,
        (),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-FROST-GATE-20261105-PLANS'),
                ('scope', 'Exact user supplied automation identity; runtime agent ID excluded.'),
            ),
        ),
    ),
    (
        'prophecies.frost_gate.identity.gear_lever',
        'item',
        ('Gear Lever',),
        (8794, 46138, 53680, 7284),
        None,
        (),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-FROST-GATE-20261105-GEAR_LEVER'),
                ('scope', 'Exact user supplied automation identity; runtime agent ID excluded.'),
            ),
        ),
    ),
    (
        'prophecies.frost_gate.identity.mechanism',
        'gadget',
        ('Lever Mechanism',),
        (8505, 62438, 52469, 2328),
        None,
        (),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-FROST-GATE-20261105-MECHANISM'),
                ('scope', 'Exact user supplied automation identity; runtime agent ID excluded.'),
            ),
        ),
    ),
)

OCCURRENCES: tuple[OccurrenceRow, ...] = (
    (
        'prophecies.npc.rornak_stonesledge.frost_gate_start.9310_-3864',
        'prophecies.frost_gate.identity.rornak',
        21,
        'The Frost Gate',
        (9310.01, -3864.39),
        (9213.7, -3910.76),
        ('USER-FROST-GATE-20261105-RORNAK_START',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-FROST-GATE-20261105-RORNAK_START'),
                (
                    'scope',
                    'Explicit user capture in Frost Gate conversion chat. Map label in capture says outpost but '
                    'gameplay is mission instance; do not infer instance type from label.',
                ),
            ),
        ),
    ),
    (
        'prophecies.npc.rornak_stonesledge.frost_gate_delivery.-3664_-8417',
        'prophecies.frost_gate.identity.rornak',
        21,
        'The Frost Gate',
        (-3664.03, -8417.38),
        (-3668.76, -8474.97),
        ('USER-FROST-GATE-20261105-RORNAK_ARRIVAL',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-FROST-GATE-20261105-RORNAK_ARRIVAL'),
                (
                    'scope',
                    'Explicit user capture in Frost Gate conversion chat. Map label in capture says outpost but '
                    'gameplay is mission instance; do not infer instance type from label.',
                ),
            ),
        ),
    ),
    (
        'prophecies.gadget.firing_lever.frost_gate.-3644_-8415',
        'prophecies.frost_gate.identity.firing_lever',
        21,
        'The Frost Gate',
        (-3644.0, -8415.0),
        (-3715.59, -8447.33),
        ('USER-FROST-GATE-20261105-FIRING_LEVER',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-FROST-GATE-20261105-FIRING_LEVER'),
                (
                    'scope',
                    'Explicit user capture in Frost Gate conversion chat. Map label in capture says outpost but '
                    'gameplay is mission instance; do not infer instance type from label.',
                ),
            ),
        ),
    ),
    (
        'prophecies.gadget.chest.frost_gate.7161_-8034',
        'prophecies.frost_gate.identity.chest',
        21,
        'The Frost Gate',
        (7161.0, -8034.0),
        None,
        ('USER-FROST-GATE-20261105-PLANS_CHEST',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-FROST-GATE-20261105-PLANS_CHEST'),
                (
                    'scope',
                    'Explicit user capture in Frost Gate conversion chat. Map label in capture says outpost but '
                    'gameplay is mission instance; do not infer instance type from label.',
                ),
            ),
        ),
    ),
    (
        'prophecies.item.secret_siege_weapon_plans.frost_gate.7100_-7958',
        'prophecies.frost_gate.identity.plans',
        21,
        'The Frost Gate',
        (7099.9, -7958.02),
        (7305.25, -7951.95),
        ('USER-FROST-GATE-20261105-PLANS',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-FROST-GATE-20261105-PLANS'),
                (
                    'scope',
                    'Explicit user capture in Frost Gate conversion chat. Map label in capture says outpost but '
                    'gameplay is mission instance; do not infer instance type from label.',
                ),
            ),
        ),
    ),
    (
        'prophecies.item.gear_lever.frost_gate.5036_-14693',
        'prophecies.frost_gate.identity.gear_lever',
        21,
        'The Frost Gate',
        (5035.67, -14693.0),
        None,
        ('USER-FROST-GATE-20261105-GEAR_LEVER',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-FROST-GATE-20261105-GEAR_LEVER'),
                (
                    'scope',
                    'Explicit user capture in Frost Gate conversion chat. Map label in capture says outpost but '
                    'gameplay is mission instance; do not infer instance type from label.',
                ),
            ),
        ),
    ),
    (
        'prophecies.gadget.lever_mechanism.frost_gate.4795_-14888',
        'prophecies.frost_gate.identity.mechanism',
        21,
        'The Frost Gate',
        (4795.0, -14888.0),
        (5109.42, -14585.95),
        ('USER-FROST-GATE-20261105-INITIAL_MECHANISM',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-FROST-GATE-20261105-INITIAL_MECHANISM'),
                (
                    'scope',
                    'Explicit user capture in Frost Gate conversion chat. Map label in capture says outpost but '
                    'gameplay is mission instance; do not infer instance type from label.',
                ),
            ),
        ),
    ),
    (
        'prophecies.gadget.lever_mechanism.frost_gate.-89_-19857',
        'prophecies.frost_gate.identity.mechanism',
        21,
        'The Frost Gate',
        (-89.0, -19857.0),
        (-86.26, -19855.01),
        ('USER-FROST-GATE-20261105-MECHANISM_1',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-FROST-GATE-20261105-MECHANISM_1'),
                (
                    'scope',
                    'Explicit user capture in Frost Gate conversion chat. Map label in capture says outpost but '
                    'gameplay is mission instance; do not infer instance type from label.',
                ),
            ),
        ),
    ),
    (
        'prophecies.gadget.lever_mechanism.frost_gate.-2203_-20159',
        'prophecies.frost_gate.identity.mechanism',
        21,
        'The Frost Gate',
        (-2203.0, -20159.0),
        (-2145.21, -20108.82),
        ('USER-FROST-GATE-20261105-MECHANISM_2',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-FROST-GATE-20261105-MECHANISM_2'),
                (
                    'scope',
                    'Explicit user capture in Frost Gate conversion chat. Map label in capture says outpost but '
                    'gameplay is mission instance; do not infer instance type from label.',
                ),
            ),
        ),
    ),
    (
        'prophecies.gadget.lever_mechanism.frost_gate.371_-21839',
        'prophecies.frost_gate.identity.mechanism',
        21,
        'The Frost Gate',
        (371.0, -21839.0),
        (421.97, -21797.56),
        ('USER-FROST-GATE-20261105-MECHANISM_3',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-FROST-GATE-20261105-MECHANISM_3'),
                (
                    'scope',
                    'Explicit user capture in Frost Gate conversion chat. Map label in capture says outpost but '
                    'gameplay is mission instance; do not infer instance type from label.',
                ),
            ),
        ),
    ),
)
