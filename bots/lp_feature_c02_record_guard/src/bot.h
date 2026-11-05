#pragma once
#include "combat.h"
#include "economy.h"
#include "protocol.h"
#include "telemetry.h"
#include "feature_state.h"
class Bot {
    lp::World world;
    lp::Memory memory;
    lp::Telemetry stats;
    bool priority_set=false;
    int executing_round=-1;
    std::uint64_t shared_read() const;
    void shared_write(std::uint64_t,int);
    bool coordinate(const lp::Snapshot&);
    void publish(const lp::Snapshot&,bool);
    void abandon(int);
    lp::Facts facts(const lp::Snapshot&,bool);
    void camp_action(lp::TurnBudget&);
    void feature_event(int,const char*,int,int=-1,int=-1);
    bool feature_leader(const lp::Snapshot&);
    void feature_update(const lp::Snapshot&,lp::TurnBudget&,bool);
    bool feature_follow(lp::TurnBudget&);
    bool feature_rally(lp::TurnBudget&);
    void feature_patrol(lp::TurnBudget&,cambc::bitboard,cambc::vec2);
    bool feature_retreat(lp::TurnBudget&);
    int feature_support(const lp::Snapshot&) const;
public:
    void play_turn();
    void stale() {++stats.stale;lp::invalidate_observations();executing_round=-1;}
    void error(const char* what) {stats.error(what);}
};
