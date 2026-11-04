#include <cambc.h>
#include "draft.h"
#include "route_plan.h"
#include <array>
#include <algorithm>
void play_draft() {
    using D=cambc::champion_draft;
    constexpr std::array preference{D::heart_of_ruin,D::marcella,D::vesper_vale,D::ren,D::vendetta,D::varg,D::ryth,D::stellar,D::prism,D::willow,D::tavi,D::cassi_and_issac};
    auto chosen=cambc::draft::current_draft(cambc::team::ally);
    if(chosen.empty())lp::prepare_draft_routes();
    for(auto pick:preference)if(std::find(chosen.begin(),chosen.end(),pick)==chosen.end()){cambc::draft::pick(pick);return;}
}
