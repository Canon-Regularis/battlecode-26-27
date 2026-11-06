#pragma once
#include "combat.h"
#include "recovery_sdk.h"
#include "economy.h"
#include "protocol.h"
#include "telemetry.h"
class Bot {
    lp::World world;
    lp::Memory memory;
    lp::Telemetry stats;
    lp::RecoveryRuntime recovery_runtime;
    lp::action::Ledger turn_ledger;
    bool priority_set=false;
    int executing_round=-1;
    std::uint64_t shared_read() const;
    void shared_write(std::uint64_t,int);
    bool coordinate(const lp::Snapshot&);
    void publish(const lp::Snapshot&,bool);
    void abandon(int);
    lp::Facts facts(const lp::Snapshot&,bool);
    void camp_action(lp::TurnBudget&);
public:
    void play_turn();
    void stale() {turn_ledger.finish();++stats.stale;lp::invalidate_observations();executing_round=-1;}
    void error(const char* what) {turn_ledger.finish();lp::invalidate_observations();stats.error(what);}
};
