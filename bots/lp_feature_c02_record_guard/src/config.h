#pragma once
namespace lp {
struct Config {
    static constexpr int loop_phase=3;
    static constexpr int loop_service=7;
    static constexpr double loop_risk=0.2;
    static constexpr double loop_opening=0.15;
    static constexpr double loop_gold=0.02;
    static constexpr int loop_reports=3;
    static constexpr int loop_expansions=768;
    static constexpr int loop_length=5;
    static constexpr int loop_beam=8;
    static constexpr int loop_altars=4;
    static constexpr int loop_candidates=24;
    static constexpr int competition_cost=4;
    static constexpr int recall_gold=300;
    static constexpr float recovery_high=0.55f;
    static constexpr float recovery_low=0.35f;
    static constexpr int bank_bag=35, bag_age=70, stall=8, task_limit=90, max_clear=90;
    static constexpr int protection_limit=12, retry=10, rally_life=12, lease=3;
    static constexpr unsigned reserve=5000, field_admission=30000;
    static constexpr int max_fields=3;
    // Paired evaluation retained the simpler local policy and distance baseline.
    static constexpr bool coordination=false, attacks=false, wards=true, value_routing=false;
    static constexpr int bank_response=8,attack_response=6,follow_distance=2;
    static constexpr int rally_freshness=3,attack_contact_loss=2,rally_retry=3;
    static constexpr int inspection_turns=8,inspection_steps=12,inspection_views=4;
    static constexpr int inspection_scan=128,inspection_queries=4,inspection_cache=32;
    static constexpr int inspection_stall=3,inspection_retry=3,guard_radius=2,patrol_radius=1;
    static constexpr int max_state_changes=4,escape_clear_turns=2,bank_reacquire=2;
    static constexpr unsigned coordination_reserve=16000,inspection_fuel=45000,ward_fuel=45000;
};
}
