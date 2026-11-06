#pragma once
#include "economic_service.h"
#include "live_turn.h"
namespace lp {
// One real public-SDK operation through the shared transaction. This does not
// acknowledge a fresh after-scene or execute a speculative continuation.
action::Result perform_service(const economic::Scene&,const economic::ServiceChoice&,LiveTurn&);
}
