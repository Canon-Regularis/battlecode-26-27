#pragma once
#include "economic_scene_sdk.h"
#include "economic_plan_sdk.h"
#include "economic_optional_sdk.h"
#include "economic_bank_sdk.h"
#include "economic_access.h"
#include "economic_service_sdk.h"
#include "recovery_sdk.h"
#include "telemetry.h"
namespace lp {
class EconomicRuntime {
    economic::Owner owner;
    EconomicCapture capture;
    EconomicPlanner planner;
    bool priority_set=false,needs_plan=false;
    unsigned scalar_writes=0;
    std::uint64_t execution=0;
    struct Failure {economic::Key key;economic::Reason reason;std::uint64_t support=0;};
    std::vector<Failure> failures;
    unsigned failure_cursor=0;
    std::array<economic::AccessQueue,128> queues{};
    void record(economic::Key,economic::Stop,economic::Reason= economic::Reason::none,
                std::uint64_t fact=0,bool work=false,float damage=0);
    bool wait_access(const economic::Scene&,const economic::Task&);
    std::pair<std::uint64_t,bool> support(const economic::Scene&,economic::Key,const action::Ledger&)const;
    void blocked(const economic::Scene&,economic::Key,economic::Stop,economic::Reason,const action::Ledger&);
    void reopen(const economic::Scene&,LiveTurn&);
    std::vector<economic::Candidate> winning_starts(const economic::Scene&,LiveTurn&);
    void recover_now(const economic::Scene&,World&,Memory&,TurnBudget&,RecoveryRuntime&,LiveTurn&,Telemetry&);
public:
    // Owns the whole live economic dispatch. No legacy selector/action footer.
    void play(World&,Memory&,TurnBudget&,RecoveryRuntime&,LiveTurn&,Telemetry&);
};
}
