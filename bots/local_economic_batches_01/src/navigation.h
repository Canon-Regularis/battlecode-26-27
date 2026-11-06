#pragma once
#include "observations.h"
#include "config.h"
#include "turn_ledger.h"
namespace lp {
enum class RouteStatus { at_goal, moved, wait, deferred, no_route_now, invalid_goals };
struct TurnBudget {
    int round;
    action::Ledger& ledger;
    int& fields;
    TurnBudget(int r,action::Ledger& l):round(r),ledger(l),fields(l.fields){}
    bool current() const {return ledger.open&&int(round_number())==round;}
    bool admit() const {return current()&&fields<1&&fuel_remaining()>=Config::field_admission;}
};
RouteStatus move_to(bitboard goals,bool safe,TurnBudget&,Memory&,bool constrained=false);
bool retreat(TurnBudget&,Memory&);
}
