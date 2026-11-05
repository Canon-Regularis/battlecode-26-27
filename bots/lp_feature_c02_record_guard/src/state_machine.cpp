#include "model.h"
namespace lp {
State decide(const Facts& f,const Memory& m) {
    if(!f.alive) return State::dead;
    if(f.tribute || f.teleport) return State::bank;
    if constexpr(Features::camp_commit)if(f.camp_valid&&f.reward&&f.occupied)return State::protect;
    if constexpr(Features::bank_commit)if(f.bank_protect)return State::protect;
#if PARTY_FEATURE_MASK & (1ULL<<5)
    if(f.attack_commit)return State::rally;
#endif
    if(f.spawn && f.threatened) return State::defend;
    if(f.danger) return State::escape;
    if(f.recalling) return f.enemy_visible||f.camp_hit ? State::escape:State::recall;
    if(f.spawn && f.hp<f.max_hp) return State::healing;
    if(f.recovery) return f.enemy_visible||f.camp_hit ? State::escape:State::recall;
    if(f.bank_needed) return State::prepare_bank;
    if(f.bank_protect) return State::protect;
    if(f.camp_valid) return f.reward&&f.occupied ? State::protect:State::capture;
    if(f.rally) return State::rally;
    if(f.leader) return State::lead;
    if(m.guidance_seen>=0) return State::follow;
    return State::explore;
}
}
