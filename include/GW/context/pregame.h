#pragma once

#include "base/error_handling.h"

#include <cstddef>
#include <cstdint>

namespace GW::Context {

    struct LoginCharacter {
        // ?? Header (0x00–0x07) ??
        uint32_t    appearance_packed;            // 0x00 packed bitfield (8 appearance fields)
        uint32_t    pvp_flag;                     // 0x04 PvP character flag
        // ?? Guild GUID (0x08–0x17) ??
        uint32_t    guild_guid_0;                 // 0x08
        uint32_t    guild_guid_1;                 // 0x0C
        uint32_t    guild_guid_2;                 // 0x10
        uint32_t    guild_guid_3;                 // 0x14
        // ?? Items TArray (0x18–0x23) ??
        void* items_data;                   // 0x18 data pointer (freed in OnNotifyClear)
        uint32_t    items_capacity;               // 0x1C
        uint32_t    items_count;                  // 0x20
        // ?? Padding (0x24–0x27) ??
        uint32_t    items_param;                  // 0x24 likely m_param or dead
        // ?? Core Data (0x28–0x2F) ??
        uint32_t    level;                        // 0x28
        uint32_t    current_map_id;               // 0x2C
        // ?? Profession & Flags (0x30–0x4B) ??
        uint32_t    field_0x30;                   // 0x30 UNRESOLVED
        uint32_t    primary_profession;           // 0x34 unpacked profession
        uint32_t    profession_enum;              // 0x38 ECharProfession
        uint32_t    field_0x3C;                   // 0x3C likely is_pvp_character
        uint32_t    field_0x40;                   // 0x40 UNRESOLVED
        uint32_t    field_0x44;                   // 0x44 UNRESOLVED
        uint32_t    field_0x48;                   // 0x48 UNRESOLVED
        // ?? Model & Name (0x4C–0x77) ??
        void* char_model_ptr;               // 0x4C CCharModel*
        wchar_t     character_name[20];           // 0x50 inline wchar_t[20]
    };
    static_assert(sizeof(LoginCharacter) == 0x78, "LoginCharacter size mismatch");

    struct PreGameContext {
        //Header (0x00–0x0B)
        uint32_t    frame_id;                        // 0x00
        uint32_t    scene_type;                      // 0x04  init 4
        uint32_t    scene_controller_iface;          // 0x08  init 0
        //Pitch Spring-Damper (0x0C–0x1B)
        float       camera_pitch_frequency;          // 0x0C  init 1.0f
        float       camera_pitch_current;            // 0x10  init 0.0f
        float       camera_pitch_target;             // 0x14  init 0.0f
        float       camera_pitch_velocity;           // 0x18  init 0.0f
        //RESERVED (0x1C–0x4B)
        uint32_t    RESERVED_0x1C[12];               // 0x1C  dead space (48 bytes)
        //Camera Mode (0x4C–0x4F)
        uint32_t    camera_mode;                     // 0x4C  init 0
        //RESERVED (0x50–0x67)
        uint32_t    RESERVED_0x50[5];                // 0x50  dead space (20 bytes)
        uint32_t    RESERVED_0x64;                   // 0x64  unanalysed (4 bytes)
        //Limits Spring-Damper (0x68–0x83)
        float       camera_limits_frequency;         // 0x68  init 1.0f
        float       camera_limits_min_current;       // 0x6C  init -0.09f
        float       camera_limits_max_current;       // 0x70  init 75.0f
        float       camera_limits_min_target;        // 0x74  init -0.09f
        float       camera_limits_max_target;        // 0x78  init 75.0f
        float       camera_limits_min_velocity;      // 0x7C  init 0.0f
        float       camera_limits_max_velocity;      // 0x80  init 0.0f
        //Scroll Offset Spring-Damper (0x84–0x93)
        float       scroll_offset_frequency;         // 0x84  init 1.0f
        float       scroll_offset_current;           // 0x88  init 100.0f
        float       scroll_offset_target;            // 0x8C  init 100.0f
        float       scroll_offset_velocity;          // 0x90  init 0.0f
        //Scroll Speed Spring-Damper (0x94–0xA3)
        float       scroll_speed_frequency;          // 0x94  init 1.0f
        float       scroll_speed_current;            // 0x98  init ~1.31f
        float       scroll_speed_target;             // 0x9C  init ~1.31f
        float       scroll_speed_velocity;           // 0xA0  init 0.0f
        //Camera Height (0xA4–0xAF)
        float       camera_height;                   // 0xA4  init 70.0f
        float       camera_height_min;               // 0xA8  init 70.0f
        float       camera_height_max;               // 0xAC  init 70.0f
        //Rotation Spring-Damper (0xB0–0xBF)
        float       camera_rotation_frequency;       // 0xB0  init 1.0f
        float       camera_rotation_current;         // 0xB4  init 0.0f
        float       camera_rotation_target;          // 0xB8  init 0.0f
        float       camera_rotation_velocity;        // 0xBC  init 0.0f
        //RESERVED (0xC0–0xCF)
        uint32_t    RESERVED_0xC0[4];                // 0xC0  dead space (16 bytes)

        //Tail (0xD0–0xFF) -DO NOT CHANGE
        uint32_t    max_characters;
        int32_t     chosen_character_index;
        int32_t     preview_character_index;
        int32_t     pending_character_index;
        LoginCharacter* chars_buffer;
        uint32_t    chars_capacity;
        uint32_t    chars_count;
        int32_t     char_creation_flag;
        int32_t     create_slot_index;
        uint32_t    sentinel_guard;
        void* self_link;
        uint32_t    list_head;
    };

    static_assert(offsetof(PreGameContext, camera_mode) == 0x4C, "PreGameContext::camera_mode offset mismatch");
    static_assert(offsetof(PreGameContext, max_characters) == 0xD0, "PreGameContext::max_characters offset mismatch");
    static_assert(sizeof(PreGameContext) == 0x100, "PreGameContext size mismatch");

}  // namespace GW::Context
