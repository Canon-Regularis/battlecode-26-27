#pragma once
#include "combat.h"
#include "recovery.h"
#include "live_turn.h"
namespace lp {
// Map/static values survive dispatches. No dynamic scene or future action is retained.
struct RecoveryRuntime {
    std::shared_ptr<const recovery::Terrain> terrain;
    struct Member {camp handle;int group;vec2 last;int range;};
    std::vector<Member> members;
    bool initialized=false;
};
recovery::Outcome recover(recovery::Intent,World&,Memory&,TurnBudget&,RecoveryRuntime&,LiveTurn&);
}
