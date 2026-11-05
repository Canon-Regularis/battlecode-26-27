#pragma once
#include "observations.h"
#include "config.h"
namespace lp {
enum class RouteStatus { at_goal, moved, wait, deferred, no_route_now, invalid_goals };
struct TurnBudget {int round,fields=0;bool current() const {return int(round_number())==round;}
    bool admit() const {return current()&&fields<Config::max_fields&&fuel_remaining()>=Config::field_admission;}};
RouteStatus move_to(bitboard goals,bool safe,TurnBudget&,Memory&,bool constrained=false,const bitboard* uncertain=nullptr,bool* overlay_empty=nullptr);
bool retreat(TurnBudget&,Memory&);
}
