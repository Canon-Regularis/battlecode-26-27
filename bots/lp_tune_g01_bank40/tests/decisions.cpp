#include "model.h"
#include "protocol.h"
#include <cstdlib>
#include <iostream>
using namespace lp;
void check(bool ok,const char* name){if(!ok){std::cerr<<"FAIL "<<name<<'\n';std::exit(1);}}
int main(){
    auto empty=wire::empty();check(wire::valid(empty,0),"zero-round initialization");check(!wire::leader_live(empty,0,6),"empty is not leader zero");
    auto first=wire::create(empty,0,10,2,12);auto replacement=wire::create(empty,1,11,2,12);
    check(!wire::same(first,replacement),"ABA replacement at identical type and chunk");
    check(wire::live(first,21,6,49)&&!wire::live(first,22,6,49),"absolute lifetime cannot refresh");
    check(!wire::live(first,9,6,49),"future request rejected");
    auto late=wire::create(empty,5,1999,1,48);check(wire::live(late,2000,6,49),"late match identity");check(!wire::valid(late,2048),"unsupported rounds never wrap");
    auto leader=wire::put(wire::put(empty,wire::leader,3,2),wire::heartbeat,11,100);
    check(wire::leader_live(leader,103,6)&&!wire::leader_live(leader,104,6),"heartbeat lease");
    check(!wire::valid(wire::put(empty,wire::version,3,2),10),"unknown protocol version");
    Facts f;Memory m;f.camp_valid=true;f.reward=true;f.occupied=true;f.danger=true;
    check(decide(f,m)==State::escape,"danger precedes protection admission");
    f.tribute=true;check(decide(f,m)==State::bank,"active channel precedes discretionary state");
    f.alive=false;check(decide(f,m)==State::dead,"death overrides channel");
    f=Facts{};f.recovery=true;f.enemy_visible=true;check(decide(f,m)==State::escape,"cannot recall in enemy vision");
    f=Facts{};f.bank_needed=true;f.camp_valid=true;check(decide(f,m)==State::prepare_bank,"saved bag before another camp");
    f=Facts{};check(decide(f,m)==State::explore,"no leader does not prevent autonomous exploration");
    check(bank_due(1,10,10+Config::bag_age,0)&&!bank_due(1,10,9+Config::bag_age,0),"small bag has age deadline");
    check(bank_due(Config::bank_bag,-1,0,0)&&!bank_due(Config::bank_bag-1,-1,0,0),"configured bag threshold");
    check(bank_due(2,10,20,998),"winning bag banks early");
    check(task_expired(Config::task_limit,0,Config::task_limit-1)&&task_expired(Config::stall,0,0)&&!task_expired(Config::stall-1,0,0),"task age and progress are independent");
    std::cout<<"PASS protocol and state scenarios\n";
}
