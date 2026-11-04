#pragma once

#include <cambc.h>
#include <cstdint>
#include <vector>

extern const char* current_bot_stage;

enum class BotState : std::uint8_t {
    lead_team, follow_leader, capture_point, protect_point, prepare_gem_banking,
    bank_gems, rally, run_away, recall, healing, defend_spawn, death
};

class Bot {
    BotState state_ = BotState::follow_leader;
    std::uint8_t slot_ = 7;
    std::uint8_t camp_target_ = 63;
    std::uint8_t altar_target_ = 63;
    cambc::vec2 last_leader_position_{};
    bool has_leader_position_ = false;
    bool bank_was_started_ = false;
    std::uint32_t last_enemy_report_round_ = 0;
    std::uint32_t shop_phase_ = 0;
    cambc::vec2 last_ward_position_{};
    std::uint8_t last_ward_anchor_ = 63;
    bool has_ward_position_ = false;
    std::uint8_t attack_lost_contact_turns_ = 0;
    bool protect_bank_ = false;
    std::uint8_t bank_carrier_slot_ = 7;

    void do_shop(bool dead = false);
    void publish_protocol(std::uint64_t& word, bool eligible);
    void run_state(std::uint64_t& word);
    void try_ward(std::uint64_t word);

public:
    void play_turn();
};

void play_draft();
