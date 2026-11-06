#pragma once
#include "economic_scene.h"
#include "live_turn.h"
namespace lp {
// Entry-only opportunity. Caller never invokes this after bank/service/recovery.
bool natural_shop(Memory&,LiveTurn&);
bool initialize_priority(int slot,LiveTurn&,bool& initialized);
// Caller supplies a fresh complete scene and has finished required actions.
bool economic_ward(const economic::Scene&,const economic::Task&,LiveTurn&);
}
