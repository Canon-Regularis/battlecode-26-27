#include <cambc.h>
#include "draft.h"
#include "route_plan.h"
#include "roster.h"
#include <algorithm>
void play_draft() {
    const auto plan=lp::roster::plan(cambc::draft::team_size());
    auto chosen=cambc::draft::current_draft(cambc::team::ally);
    if(chosen.empty())lp::prepare_draft_routes(plan);
    for(auto pick:plan.preferences)if(std::find(chosen.begin(),chosen.end(),pick)==chosen.end()){cambc::draft::pick(pick);return;}
}
