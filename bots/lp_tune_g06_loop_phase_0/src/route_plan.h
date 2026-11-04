#pragma once
#include "objectives.h"
namespace lp {
void prepare_draft_routes();
void load_draft_routes(World&);
int preferred_loop_camp(World&,const std::vector<bool>& eligible);
void advance_loop(World&,int completed);
}
