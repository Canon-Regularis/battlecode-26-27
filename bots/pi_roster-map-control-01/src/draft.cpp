#include <cambc.h>
#include "draft.h"
#include "route_plan.h"
#include "roster.h"
#include <algorithm>
void play_draft() {
    constexpr auto preference=lp::roster::preferences;
    auto chosen=cambc::draft::current_draft(cambc::team::ally);
    if(chosen.empty())lp::prepare_draft_routes();
    for(auto pick:preference)if(std::find(chosen.begin(),chosen.end(),pick)==chosen.end()){cambc::draft::pick(pick);return;}
}
