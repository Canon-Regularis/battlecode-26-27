#pragma once
namespace lp {
struct Config {
    static constexpr int loop_phase=2;
    static constexpr int loop_service=7;
    static constexpr double loop_risk=0.2;
    static constexpr double loop_opening=0.15;
    static constexpr double loop_gold=0.02;
    static constexpr int loop_reports=3;
    static constexpr int loop_expansions=768;
    static constexpr int loop_length=5;
    static constexpr int loop_beam=4;
    static constexpr int loop_altars=4;
    static constexpr int loop_candidates=24;
    static constexpr int competition_cost=4;
    static constexpr int recall_gold=300;
    static constexpr float recovery_high=0.55f;
    static constexpr float recovery_low=0.35f;
    static constexpr int bank_bag=35, bag_age=70, stall=8, task_limit=90, max_clear=90;
    static constexpr int protection_limit=12, retry=10, rally_life=6, lease=3;
    static constexpr unsigned reserve=10000, field_admission=55000;
    static constexpr int max_fields=3;
    // Paired evaluation retained the simpler local policy and distance baseline.
    static constexpr bool coordination=true, attacks=false, wards=true, value_routing=false;
};
}
