#pragma once
#include "economic_fields_sdk.h"
#include "economic_ranking_sdk.h"
namespace lp {
enum class PlanStatus { ready, planning, deferred, no_task, exposed, unavailable, capacity, stale };
struct EconomicPlan {
    PlanStatus status=PlanStatus::deferred;
    economic::Directive directive;
    economic::RouteResult route;
};
// SDK/native geometry -> frozen scalar ranking -> committed owner -> retained
// route. One field is moved into extraction; no second compute or field copy.
class EconomicPlanner {
    enum class Stage { field, candidates, extract } stage=Stage::field;
    EconomicFields fields;
    economic::Candidates candidates;
    economic::Scene frozen;
    economic::RankingSettings settings;
    economic::Directive selected;
    bool have_frozen=false;
public:
    economic::Route route;
    EconomicPlan prepare(World&,const economic::Scene&,economic::Owner&,LiveTurn&,
        unsigned& shared_scalar_writes,bool repair=false);
    void cancel_pending();
};
}
