#include "economic_ranking_sdk.h"
#include <cmath>
namespace lp {
economic::RankingSettings ranking_settings(const economic::Scene& scene,LiveTurn& turn) {
    turn.check();if(scene.economy.self.epoch!=turn.epoch())throw TurnExpired{};
    economic::RankingSettings out;
    out.capture_time=constants::capture_time;out.submit_range=constants::submit_gems_range;
    out.winning_gems=constants::winning_gems;
    out.submission_available=!turn.ledger().submit_attempted;
    out.duration_supported=constants::submit_gem_duration_multiplier==0.1&&
        constants::submit_gem_base_duration==0&&constants::submit_gem_minimum_duration==1;
    const auto inventory=turn.read([]{return self().item_count();});
    for(auto item:{item_type::tribute_emblem_of_strength,item_type::tribute_emblem_of_focus,item_type::tribute_emblem_of_health}) {
        if(!inventory[item])continue;
        const auto metadata=turn.read([&]{return item.info();});
        out.tribute=true;
        if(metadata.passive!=item_passive::tribute||!std::isfinite(metadata.passive_magnitude)||
            metadata.passive_magnitude!=0.33f)out.duration_supported=false;
        break; // family effects do not stack
    }
    for(auto item:{item_type::capture_emblem_of_strength,item_type::capture_emblem_of_focus,item_type::capture_emblem_of_health}) {
        if(!inventory[item])continue;
        const auto metadata=turn.read([&]{return item.info();});
        if(metadata.passive==item_passive::capture&&metadata.passive_magnitude==3.0f)out.capture_cap=3;
        else out.capture_supported=false; // unpriced, never a clear prohibition
        break;
    }
    turn.check();if(scene.economy.self.epoch!=turn.epoch())throw TurnExpired{};
    return out;
}
}
