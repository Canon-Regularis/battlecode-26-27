#include "economic_access.h"
#include <iostream>
#include <stdexcept>
using namespace lp::economic;
unsigned checks=0;
#define CHECK(...) do{++checks;if(!(__VA_ARGS__))throw std::runtime_error("line "+std::to_string(__LINE__)+": " #__VA_ARGS__);}while(0)
Scene scene() {
    Scene s;s.width=s.height=16;s.economy.complete=true;
    auto& own=s.economy.self;own.alive=true;own.epoch={2,0,10,0};own.pos={7,7};own.bag=10;
    s.altars={{9,7}};s.visible.fill(1);s.occupied.fill(1);s.blocked.fill(1);
    s.blocked[s.local(own.pos)]=s.blocked[s.local({8,7})]=0;
    Champion a;a.key=1;a.alive=true;a.pos={8,7};a.bag=20;s.allies={a};return s;
}
int main(){try {
    auto s=scene();AccessQueue courtesy;
    CHECK(courtesy.wait(s,0,1));CHECK(courtesy.wait(s,0,1));
    ++s.economy.self.epoch.round;CHECK(!courtesy.wait(s,0,1)); // no actual progress
    ++s.economy.self.epoch.round;CHECK(!courtesy.wait(s,0,1));
    ++s.economy.self.epoch.round;CHECK(!courtesy.wait(s,0,1));
    s.allies[0].channel=true;s.allies[0].timer=5;CHECK(!courtesy.wait(s,0,1));
    // Lost sight cannot create a new access episode; observed vacancy can.
    s.visible.fill(0);CHECK(!courtesy.wait(s,0,1));
    s.visible.fill(1);s.blocked[s.local({8,8})]=0;s.occupied[s.local({8,8})]=0;CHECK(!courtesy.wait(s,0,1));
    s.blocked[s.local({8,8})]=1;s.occupied.fill(1);CHECK(courtesy.wait(s,0,1));
    ++s.economy.self.epoch.round;--s.allies[0].timer;CHECK(courtesy.wait(s,0,1));
    ++s.economy.self.epoch.round;CHECK(!courtesy.wait(s,0,1)); // no timer progress
    ++s.economy.self.epoch.round;--s.allies[0].timer;CHECK(!courtesy.wait(s,0,1));
    s=scene();AccessQueue promotion;CHECK(promotion.wait(s,0,1));
    ++s.economy.self.epoch.round;s.allies[0].channel=true;s.allies[0].timer=2;
    CHECK(promotion.wait(s,0,1));
    ++s.economy.self.epoch.round;--s.allies[0].timer;CHECK(promotion.wait(s,0,1));
    ++s.economy.self.epoch.round;s.allies[0].timer=3;CHECK(!promotion.wait(s,0,1)); // restart
    s=scene();AccessQueue changed;CHECK(changed.wait(s,0,1));
    ++s.economy.self.epoch.round;s.allies[0].key=3;CHECK(!changed.wait(s,0,1));
    s=scene();AccessQueue deadline;s.allies[0].channel=true;s.allies[0].timer=2;
    CHECK(deadline.wait(s,0,1));s.economy.self.epoch.round+=4;s.allies[0].timer=1;
    CHECK(!deadline.wait(s,0,1)); // timer progress cannot extend fixed deadline
    s=scene();AccessQueue denied;s.economy.self.completed=true;CHECK(!denied.wait(s,0,1));
    s.economy.self.completed=false;s.allies[0].bag=1;CHECK(!denied.wait(s,0,1));
    s.allies[0].bag=10;s.allies[0].key=3;CHECK(!denied.wait(s,0,1));
    s.allies[0].key=1;CHECK(denied.wait(s,0,1));
    std::cout<<"PASS: "<<checks<<" finite physical-access queue assertions\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
