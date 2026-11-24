"""Generated static interaction catalog partition. Do not edit rows in isolation."""

from __future__ import annotations

from .schema import IdentityRow
from .schema import OccurrenceRow

PARTITION = "prophecies_althea"

IDENTITIES: tuple[IdentityRow, ...] = (
    (
        'prophecies.althea_recruitment.identity.althea_breach',
        'npc',
        ('Ghost of Althea',),
        None,
        ('npc', 'GHOST_OF_ALTHEA', 2),
        (8940,),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-CHAT-ALTHEA-ALTHEA-BREACH'),
                ('scope', 'Directly supplied capture field; prophecies.npc.ghost_of_althea.the_breach.18232_-1550'),
            ),
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-CHAT-ALTHEA-REWARD-ALTHEA'),
                (
                    'scope',
                    'Directly supplied capture field; ' 'prophecies.npc.ghost_of_althea.reward_level_3.-16098_-8626',
                ),
            ),
        ),
    ),
    (
        'prophecies.althea_recruitment.identity.althea_level_1',
        'npc',
        ('Ghost of Althea',),
        None,
        ('npc', 'GHOST_OF_ALTHEA', 1),
        (8940,),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-CHAT-ALTHEA-ALTHEA-LEVEL-1'),
                (
                    'scope',
                    'Directly supplied capture field; '
                    'prophecies.npc.ghost_of_althea.elegy_reward_level_1.-7400_-9462',
                ),
            ),
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-CHAT-ALTHEA-ALTHEA-ALLY-LEVEL-2'),
                ('scope', 'Directly supplied capture field; prophecies.npc.ghost_of_althea.escort_level_2.-6741_8818'),
            ),
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-CHAT-ALTHEA-ALTHEA-ALLY-LEVEL-3'),
                ('scope', 'Directly supplied capture field; prophecies.npc.ghost_of_althea.escort_level_3.-16318_1777'),
            ),
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-CHAT-ALTHEA-ALTHEA-COST-INTRO-LEVEL-1'),
                (
                    'scope',
                    'Directly supplied capture field; ' 'prophecies.npc.ghost_of_althea.cost_intro_level_1.-7400_-9462',
                ),
            ),
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-CHAT-ALTHEA-ALTHEA-COST-REWARD-LEVEL-1'),
                (
                    'scope',
                    'Directly supplied capture field; '
                    'prophecies.npc.ghost_of_althea.cost_reward_level_1.-7400_-9462',
                ),
            ),
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-CHAT-ALTHEA-ALTHEA-DREAMER-ACCEPT-LEVEL-1'),
                (
                    'scope',
                    'Directly supplied capture field; '
                    'prophecies.npc.ghost_of_althea.dreamer_accept_level_1.-7400_-9462',
                ),
            ),
        ),
    ),
    (
        'prophecies.althea_recruitment.identity.kopp_piken',
        'npc',
        ('Kopp the Quick',),
        (33026, 15594, 37397, 6126),
        None,
        (8941,),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-CHAT-ALTHEA-KOPP-PIKEN'),
                ('scope', 'Directly supplied capture field; prophecies.npc.kopp_the_quick.piken_square.22910_10414'),
            ),
        ),
    ),
    (
        'prophecies.althea_recruitment.identity.duke_level_2',
        'npc',
        ('Duke Willgrove',),
        None,
        ('npc', 'DUKE_WILLGROVE', 0),
        (8942,),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-CHAT-ALTHEA-DUKE-LEVEL-2'),
                (
                    'scope',
                    'Directly supplied capture field; ' 'prophecies.npc.duke_willgrove.tunnels_level_2.-16560_9071',
                ),
            ),
        ),
    ),
    (
        'prophecies.althea_recruitment.identity.phantom',
        'npc',
        ('Enraged Phantom',),
        (33026, 15679, 35913, 47401, 13285),
        None,
        (9059,),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-CHAT-ALTHEA-PHANTOM'),
                (
                    'scope',
                    'Directly supplied capture field; ' 'prophecies.npc.enraged_phantom.tunnels_level_3.-12437_-5913',
                ),
            ),
        ),
    ),
    (
        'prophecies.althea_recruitment.identity.varny',
        'npc',
        ('Varny the Zealot',),
        (33026, 15597, 44938, 37568, 672),
        None,
        (9071,),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-CHAT-ALTHEA-VARNY'),
                (
                    'scope',
                    'Directly supplied capture field; ' 'prophecies.npc.varny_the_zealot.tunnels_level_3.-13690_-9235',
                ),
            ),
        ),
    ),
    (
        'prophecies.althea_recruitment.identity.chest',
        'gadget',
        ("Zealot's Chest",),
        None,
        ('gadget', 'ZEALOT_S_CHEST', 0),
        (),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-CHAT-ALTHEA-CHEST'),
                (
                    'scope',
                    'Directly supplied capture field; ' 'prophecies.gadget.zealots_chest.tunnels_level_3.-16068_-8484',
                ),
            ),
        ),
    ),
    (
        'prophecies.althea_recruitment.identity.keystone',
        'item',
        ('Elemental Keystone',),
        (33026, 15454),
        None,
        (38301,),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-CHAT-ALTHEA-KEYSTONE'),
                (
                    'scope',
                    'Directly supplied capture field; '
                    'prophecies.item.elemental_keystone.tunnels_level_1.-8822_-4361',
                ),
            ),
        ),
    ),
)

OCCURRENCES: tuple[OccurrenceRow, ...] = (
    (
        'prophecies.npc.ghost_of_althea.the_breach.18232_-1550',
        'prophecies.althea_recruitment.identity.althea_breach',
        102,
        '102',
        (18232.0, -1550.0),
        (18225.55, -1613.24),
        ('USER-CHAT-ALTHEA-ALTHEA-BREACH',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-CHAT-ALTHEA-ALTHEA-BREACH'),
                ('source_field', 'althea_breach'),
                (
                    'scope',
                    'Exact supplied NPC/item/gadget capture in this chat, including encoded identity, map, target '
                    'and player approach; sub-ID labels that existing field, not a new run.',
                ),
            ),
        ),
    ),
    (
        'prophecies.npc.ghost_of_althea.elegy_reward_level_1.-7400_-9462',
        'prophecies.althea_recruitment.identity.althea_level_1',
        880,
        '880',
        (-7400.0, -9462.0),
        (-7432.14, -9520.42),
        ('USER-CHAT-ALTHEA-ALTHEA-LEVEL-1',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-CHAT-ALTHEA-ALTHEA-LEVEL-1'),
                ('source_field', 'althea_level_1'),
                (
                    'scope',
                    'Exact supplied NPC/item/gadget capture in this chat, including encoded identity, map, target '
                    'and player approach; sub-ID labels that existing field, not a new run.',
                ),
            ),
        ),
    ),
    (
        'prophecies.npc.kopp_the_quick.piken_square.22910_10414',
        'prophecies.althea_recruitment.identity.kopp_piken',
        40,
        '40',
        (22910.0, 10414.0),
        (22864.04, 10358.94),
        ('USER-CHAT-ALTHEA-KOPP-PIKEN',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-CHAT-ALTHEA-KOPP-PIKEN'),
                ('source_field', 'kopp_piken'),
                (
                    'scope',
                    'Exact supplied NPC/item/gadget capture in this chat, including encoded identity, map, target '
                    'and player approach; sub-ID labels that existing field, not a new run.',
                ),
            ),
        ),
    ),
    (
        'prophecies.npc.duke_willgrove.tunnels_level_2.-16560_9071',
        'prophecies.althea_recruitment.identity.duke_level_2',
        881,
        '881',
        (-16560.0, 9071.0),
        (-16537.54, 9147.32),
        ('USER-CHAT-ALTHEA-DUKE-LEVEL-2',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-CHAT-ALTHEA-DUKE-LEVEL-2'),
                ('source_field', 'duke_level_2'),
                (
                    'scope',
                    'Exact supplied NPC/item/gadget capture in this chat, including encoded identity, map, target '
                    'and player approach; sub-ID labels that existing field, not a new run.',
                ),
            ),
        ),
    ),
    (
        'prophecies.npc.enraged_phantom.tunnels_level_3.-12437_-5913',
        'prophecies.althea_recruitment.identity.phantom',
        882,
        '882',
        (-12436.51, -5912.76),
        (-12276.06, -6133.13),
        ('USER-CHAT-ALTHEA-PHANTOM',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-CHAT-ALTHEA-PHANTOM'),
                ('source_field', 'phantom'),
                (
                    'scope',
                    'Exact supplied NPC/item/gadget capture in this chat, including encoded identity, map, target '
                    'and player approach; sub-ID labels that existing field, not a new run.',
                ),
            ),
        ),
    ),
    (
        'prophecies.item.boss_key.tunnels_level_3.-12437_-5913',
        'eotn.item.boss_key_s.enc_8102_1bcb_fd25_ce28_03fc',
        882,
        '882',
        (-12436.51, -5912.76),
        (-12353.09, -5627.28),
        ('USER-CHAT-ALTHEA-BOSS-KEY',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-CHAT-ALTHEA-BOSS-KEY'),
                ('source_field', 'boss_key'),
                (
                    'scope',
                    'Exact supplied NPC/item/gadget capture in this chat, including encoded identity, map, target '
                    'and player approach; sub-ID labels that existing field, not a new run.',
                ),
            ),
            (
                ('source_type', 'existing_identity_reference'),
                ('identity_key', 'eotn.item.boss_key_s.enc_8102_1bcb_fd25_ce28_03fc'),
                ('source_partition', 'eotn_dungeons'),
                (
                    'scope',
                    'This is a new directly captured Ascalon item occurrence, not borrowed occurrence geometry. '
                    'Its freshly supplied encoded identity exactly equals the already cataloged identity '
                    'definition; retain that single identity owner. Existing identity has no prior occurrence to '
                    'reference. No missing observation or lifecycle proof is inferred.',
                ),
            ),
        ),
    ),
    (
        'prophecies.gadget.boss_lock.tunnels_level_3.-6471_-4283',
        'eotn.gadget.boss_lock.enc_8102_1981_ce48_8f16_5dee',
        882,
        '882',
        (-6471.0, -4283.0),
        (-6399.24, -4238.74),
        ('USER-CHAT-ALTHEA-BOSS-LOCK',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-CHAT-ALTHEA-BOSS-LOCK'),
                ('source_field', 'boss_lock'),
                (
                    'scope',
                    'Exact supplied NPC/item/gadget capture in this chat, including encoded identity, map, target '
                    'and player approach; sub-ID labels that existing field, not a new run.',
                ),
            ),
            (
                ('source_type', 'identity_reuse'),
                (
                    'reference_occurrence',
                    'eotn.gadget.boss_lock.enc_8102_1981_ce48_8f16_5dee.vloxen_excavations_level_1.-2393_-15743',
                ),
                (
                    'scope',
                    'Exact encoded identity, visible name and gadget kind match the existing catalog identity. '
                    'Ascalon geometry is freshly independently captured; no lifecycle/live-success proof '
                    'transferred.',
                ),
            ),
        ),
    ),
    (
        'prophecies.npc.varny_the_zealot.tunnels_level_3.-13690_-9235',
        'prophecies.althea_recruitment.identity.varny',
        882,
        '882',
        (-13689.87, -9234.63),
        (-13802.52, -8128.91),
        ('USER-CHAT-ALTHEA-VARNY',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-CHAT-ALTHEA-VARNY'),
                ('source_field', 'varny'),
                (
                    'scope',
                    'Exact supplied NPC/item/gadget capture in this chat, including encoded identity, map, target '
                    'and player approach; sub-ID labels that existing field, not a new run.',
                ),
            ),
        ),
    ),
    (
        'prophecies.npc.ghost_of_althea.reward_level_3.-16098_-8626',
        'prophecies.althea_recruitment.identity.althea_breach',
        882,
        '882',
        (-16098.0, -8626.0),
        (-16017.32, -8622.57),
        ('USER-CHAT-ALTHEA-REWARD-ALTHEA',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-CHAT-ALTHEA-REWARD-ALTHEA'),
                ('source_field', 'reward_althea'),
                (
                    'scope',
                    'Exact supplied NPC/item/gadget capture in this chat, including encoded identity, map, target '
                    'and player approach; sub-ID labels that existing field, not a new run.',
                ),
            ),
            (
                ('source_type', 'identity_reuse'),
                ('reference_occurrence', 'prophecies.npc.ghost_of_althea.the_breach.18232_-1550'),
                (
                    'scope',
                    'Matching exact encoded identity, Ghost of Althea name, NPC kind and diagnostic model8940 '
                    'independently supplied in each role capture; map, role and approach remain '
                    'occurrence-specific.',
                ),
            ),
        ),
    ),
    (
        'prophecies.gadget.zealots_chest.tunnels_level_3.-16068_-8484',
        'prophecies.althea_recruitment.identity.chest',
        882,
        '882',
        (-16068.0, -8484.0),
        (-16030.24, -8551.14),
        ('USER-CHAT-ALTHEA-CHEST',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-CHAT-ALTHEA-CHEST'),
                ('source_field', 'chest'),
                (
                    'scope',
                    'Exact supplied NPC/item/gadget capture in this chat, including encoded identity, map, target '
                    'and player approach; sub-ID labels that existing field, not a new run.',
                ),
            ),
        ),
    ),
    (
        'prophecies.item.elemental_keystone.tunnels_level_1.-8822_-4361',
        'prophecies.althea_recruitment.identity.keystone',
        880,
        'Tunnels of the Forsaken Level1',
        (-8822.4, -4360.81),
        (-8839.8, -4612.82),
        ('USER-CHAT-ALTHEA-KEYSTONE',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-CHAT-ALTHEA-KEYSTONE'),
                ('source_field', 'keystone'),
                (
                    'scope',
                    'Exact supplied NPC/item/gadget capture in this chat, including encoded identity, map, target '
                    'and player approach; sub-ID labels that existing field, not a new run.',
                ),
            ),
        ),
    ),
    (
        'prophecies.npc.ghost_of_althea.escort_level_2.-6741_8818',
        'prophecies.althea_recruitment.identity.althea_level_1',
        881,
        '881',
        (-6741.23, 8818.46),
        (-6396.04, 9213.32),
        ('USER-CHAT-ALTHEA-ALTHEA-ALLY-LEVEL-2',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-CHAT-ALTHEA-ALTHEA-ALLY-LEVEL-2'),
                ('source_field', 'althea_ally_level_2'),
                (
                    'scope',
                    'Exact supplied NPC/item/gadget capture in this chat, including encoded identity, map, target '
                    'and player approach; sub-ID labels that existing field, not a new run.',
                ),
            ),
            (
                ('source_type', 'identity_reuse'),
                ('reference_occurrence', 'prophecies.npc.ghost_of_althea.elegy_reward_level_1.-7400_-9462'),
                (
                    'scope',
                    'Matching exact encoded identity, Ghost of Althea name, NPC kind and diagnostic model8940 '
                    'independently supplied in each role capture; map, role and approach remain '
                    'occurrence-specific.',
                ),
            ),
        ),
    ),
    (
        'prophecies.npc.ghost_of_althea.escort_level_3.-16318_1777',
        'prophecies.althea_recruitment.identity.althea_level_1',
        882,
        '882',
        (-16317.99, 1776.8),
        (-16302.0, 2451.0),
        ('USER-CHAT-ALTHEA-ALTHEA-ALLY-LEVEL-3',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-CHAT-ALTHEA-ALTHEA-ALLY-LEVEL-3'),
                ('source_field', 'althea_ally_level_3'),
                (
                    'scope',
                    'Exact supplied NPC/item/gadget capture in this chat, including encoded identity, map, target '
                    'and player approach; sub-ID labels that existing field, not a new run.',
                ),
            ),
            (
                ('source_type', 'identity_reuse'),
                ('reference_occurrence', 'prophecies.npc.ghost_of_althea.elegy_reward_level_1.-7400_-9462'),
                (
                    'scope',
                    'Matching exact encoded identity, Ghost of Althea name, NPC kind and diagnostic model8940 '
                    'independently supplied in each role capture; map, role and approach remain '
                    'occurrence-specific.',
                ),
            ),
        ),
    ),
    (
        'prophecies.npc.ghost_of_althea.cost_intro_level_1.-7400_-9462',
        'prophecies.althea_recruitment.identity.althea_level_1',
        880,
        '880',
        (-7400.0, -9462.0),
        (-7457.21, -9408.43),
        ('USER-CHAT-ALTHEA-ALTHEA-COST-INTRO-LEVEL-1',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-CHAT-ALTHEA-ALTHEA-COST-INTRO-LEVEL-1'),
                ('source_field', 'althea_cost_intro_level_1'),
                (
                    'scope',
                    'Exact supplied NPC/item/gadget capture in this chat, including encoded identity, map, target '
                    'and player approach; sub-ID labels that existing field, not a new run.',
                ),
            ),
            (
                ('source_type', 'identity_reuse'),
                ('reference_occurrence', 'prophecies.npc.ghost_of_althea.elegy_reward_level_1.-7400_-9462'),
                (
                    'scope',
                    'Matching exact encoded identity, Ghost of Althea name, NPC kind and diagnostic model8940 '
                    'independently supplied in each role capture; map, role and approach remain '
                    'occurrence-specific.',
                ),
            ),
        ),
    ),
    (
        'prophecies.npc.ghost_of_althea.cost_reward_level_1.-7400_-9462',
        'prophecies.althea_recruitment.identity.althea_level_1',
        880,
        '880',
        (-7400.0, -9462.0),
        (-7456.79, -9407.78),
        ('USER-CHAT-ALTHEA-ALTHEA-COST-REWARD-LEVEL-1',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-CHAT-ALTHEA-ALTHEA-COST-REWARD-LEVEL-1'),
                ('source_field', 'althea_cost_reward_level_1'),
                (
                    'scope',
                    'Exact supplied NPC/item/gadget capture in this chat, including encoded identity, map, target '
                    'and player approach; sub-ID labels that existing field, not a new run.',
                ),
            ),
            (
                ('source_type', 'identity_reuse'),
                ('reference_occurrence', 'prophecies.npc.ghost_of_althea.elegy_reward_level_1.-7400_-9462'),
                (
                    'scope',
                    'Matching exact encoded identity, Ghost of Althea name, NPC kind and diagnostic model8940 '
                    'independently supplied in each role capture; map, role and approach remain '
                    'occurrence-specific.',
                ),
            ),
        ),
    ),
    (
        'prophecies.npc.ghost_of_althea.dreamer_accept_level_1.-7400_-9462',
        'prophecies.althea_recruitment.identity.althea_level_1',
        880,
        '880',
        (-7400.0, -9462.0),
        (-7454.02, -9403.1),
        ('USER-CHAT-ALTHEA-ALTHEA-DREAMER-ACCEPT-LEVEL-1',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-CHAT-ALTHEA-ALTHEA-DREAMER-ACCEPT-LEVEL-1'),
                ('source_field', 'althea_dreamer_accept_level_1'),
                (
                    'scope',
                    'Exact supplied NPC/item/gadget capture in this chat, including encoded identity, map, target '
                    'and player approach; sub-ID labels that existing field, not a new run.',
                ),
            ),
            (
                ('source_type', 'identity_reuse'),
                ('reference_occurrence', 'prophecies.npc.ghost_of_althea.elegy_reward_level_1.-7400_-9462'),
                (
                    'scope',
                    'Matching exact encoded identity, Ghost of Althea name, NPC kind and diagnostic model8940 '
                    'independently supplied in each role capture; map, role and approach remain '
                    'occurrence-specific.',
                ),
            ),
        ),
    ),
)
