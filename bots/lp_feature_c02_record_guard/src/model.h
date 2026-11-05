#pragma once
#include <algorithm>
#include <array>
#include <cstdint>
#include "config.h"
#include "feature_flags.h"
namespace lp {
enum class State { lead, follow, capture, protect, prepare_bank, bank, rally,
                   escape, recall, healing, defend, dead, explore };
inline constexpr std::array names{"LEAD_TEAM","FOLLOW_LEADER","CAPTURE_POINT","PROTECT_POINT",
    "PREPARE_GEM_BANKING","BANK_GEMS","RALLY","RUN_AWAY","RECALL","HEALING","DEFEND_SPAWN","DEATH","EXPLORE"};
struct Facts {
    bool alive=true, tribute=false, recalling=false, teleport=false, spawn=false;
    bool danger=false, threatened=false, enemy_visible=false, camp_hit=false;
    bool recovery=false, bank_needed=false, camp_valid=false, reward=false, occupied=false;
    bool leader=false, rally=false, bank_protect=false;
#if PARTY_FEATURE_MASK & (1ULL<<5)
    bool attack_commit=false;
#endif
    float hp=1, max_hp=1;
};
struct Memory {
    State state=State::explore;
    int task=-1, altar=-1, task_started=0, progressed=0, protection_started=0;
    int bag_since=-1, prior_bag=0, life=0, bank_bag=0, bank_score=0;
    int shop_phase=0, shop_target=0, blocked=0, last_created=-100, rally_retry=0;
    int carrier=-1, carrier_seen=0, protection_until=0, guidance_seen=-100;
    int exploration=-1, exploration_started=0, last_distance=65535;
    int pending_altar=-1, queue_started=-1;
    bool recovering=false, was_alive=true;
    std::uint64_t owned=0;
};
State decide(const Facts&, const Memory&);
inline bool task_expired(int round,int started,int progress) {
    return round-started>=Config::task_limit || round-progress>=Config::stall;
}
inline bool bank_due(int bag,int since,int round,int score,int travel=20,int channel=0) {
    return bag>0 && (bag>=Config::bank_bag || (since>=0 && round-since>=Config::bag_age) || score+bag>=1000 ||
        round+travel+std::max(channel,(bag+9)/10)+5>=2000);
}
}
