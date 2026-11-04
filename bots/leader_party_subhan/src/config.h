#pragma once
namespace lp {
struct Config {
    static constexpr int bank_bag=20, bag_age=40, stall=8, task_limit=90, max_clear=90;
    static constexpr int protection_limit=12, retry=10, rally_life=12, lease=3;
    static constexpr unsigned reserve=10000, field_admission=55000;
    static constexpr int max_fields=3;
    // Paired evaluation retained the simpler local policy and distance baseline.
    static constexpr bool coordination=false, attacks=false, wards=true, value_routing=false;
};
}
