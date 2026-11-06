#pragma once
#include "economic_runtime_sdk.h"
class Bot {
    lp::World world;
    lp::Memory memory;
    lp::Telemetry stats;
    lp::RecoveryRuntime recovery_runtime;
    lp::action::Ledger turn_ledger;
    lp::EconomicRuntime economy;
    int executing_round=-1;
public:
    void play_turn();
    void stale() {turn_ledger.finish();++stats.stale;lp::invalidate_observations();executing_round=-1;}
    void error(const char* what) {turn_ledger.finish();lp::invalidate_observations();stats.error(what);}
};
