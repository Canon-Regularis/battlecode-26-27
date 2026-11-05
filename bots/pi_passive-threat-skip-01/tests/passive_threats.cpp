#include "navigation.h"
#include <cstdlib>
#include <iostream>
using namespace lp;
void require(bool ok,const char* label) {if(!ok){std::cerr<<"FAIL: "<<label<<'\n';std::exit(1);}}
void reset(std::vector<camp> camps) {
    fake::camps=std::move(camps);fake::enemies.clear();fake::me=champion{};
    fake::occupied={};fake::field_blocked={};fake::moves=0;fake::fields=0;fake::enumerations=0;
    for(const auto& c:fake::camps)if(c.alive)fake::occupied.set(c.pos);
    invalidate_observations();
}
void clear_calls(){for(auto& c:fake::camps)c.calls.clear();}
void expect_calls(const std::vector<std::string>& expected) {
    require(expected.size()==fake::camps.size(),"trace size");
    for(unsigned i=0;i<expected.size();++i) {
        auto trace=fake::camps[i].calls;
        // C++ does not order around(position(), attack_range()) arguments.
        // Keep both queries, allowing either evaluation order for this pair.
        for(auto p=trace.find("RP");p!=std::string::npos;p=trace.find("RP"))trace.replace(p,2,"PR");
        if(trace!=expected[i])std::cerr<<"camp "<<i<<": got "<<trace<<", expected "<<expected[i]<<'\n';
        require(trace==expected[i],"live-query order/count (unordered geometry pair)");
    }
}
RouteStatus scan_move(vec2 goal,bool safe=true) {
    bitboard goals;goals.set(goal);TurnBudget b{round_number()};Memory m;
    return move_to(goals,safe,b,m);
}
int main() {
    int cases=0;
    for(auto type:{camp_type::gem_cluster,camp_type::gold_cluster})for(int state=0;state<3;++state) {
        // Dead, sleeping, awake: an adjacent passive with an internal range of 3.
        reset({{type,state!=0,state==2,0,{6,5},3,{}}});
        require(incoming_at({5,5},{})==0,"passive incoming is zero");expect_calls({""});
        const auto& s=observe();require(!s.camp_hit&&s.incoming==0&&s.risk.is_empty(),"passive observation is harmless");
        require(s.blocked.is_set({6,5})==(state!=0),"living passive occupancy retained");expect_calls({""});
        require(scan_move({7,5})==RouteStatus::no_route_now,"passive range does not block goal");
        require(fake::field_blocked==s.blocked,"safe mask adds no passive danger");expect_calls({""});
        require(fake::enumerations==4,"all original camp enumerations retained");
        if(state!=0) {
            int fields=fake::fields;
            require(scan_move({6,5})==RouteStatus::invalid_goals,"occupied passive destination rejected");
            require(scan_move({6,5},false)==RouteStatus::invalid_goals,"unsafe movement also retains occupancy");
            require(fake::fields==fields&&fake::moves==0,"occupied goal never reaches pathfinding or movement");
            expect_calls({""});
        }
        ++cases;
    }
    // All attacking kinds, including zero strength and an out-of-range awake camp.
    for(auto type:{camp_type::wolf,camp_type::elk,camp_type::monolith,camp_type::golem}) {
        reset({{camp_type::gem_cluster,true,true,0,{4,5},3,{}},
               {type,true,true,20,{6,5},1,{}},
               {type,true,false,60,{7,7},4,{}},
               {type,false,false,60,{8,8},4,{}},
               {type,true,true,0,{9,9},4,{}},
               {type,true,true,30,{12,12},1,{}},
               {camp_type::gold_cluster,true,false,0,{5,4},3,{}}});
        champion enemy;enemy.pos={5,6};fake::enemies={enemy};
        require(incoming_at({5,5},fake::enemies)==31,"mixed damage sum unchanged");
        expect_calls({"","LWSPRS","LW","L","LWS","LWSPR",""});clear_calls();
        const auto& s=observe();require(s.camp_hit&&s.incoming==31,"awake damaging camp hits");
        auto expected_risk=around(enemy.pos,enemy.range+1);
        require(s.risk==expected_risk,"enemy danger mask unchanged");
        expect_calls({"","LWSPRLWSPRS","LWLW","LL","LWSLWS","LWSPRLWSPR",""});clear_calls();
        require(scan_move({14,2})==RouteStatus::no_route_now,"mixed safe scan reaches field");
        auto expected_blocked=s.blocked|s.risk|around({6,5},1)|around({12,12},1);
        expected_blocked.set(s.pos,false);
        require(fake::field_blocked==expected_blocked,"exact safe blocking mask");
        expect_calls({"","LWSPR","LW","L","LWS","LWSPR",""});
        require(fake::field_blocked.is_set({4,5})&&fake::field_blocked.is_set({5,4}),"mixed passive occupancy retained");
        ++cases;
    }
    // Sleeping/dead attackers in isolation must not set camp_hit or range masks.
    for(int state=0;state<2;++state) {
        reset({{camp_type::wolf,state!=0,false,20,{6,5},3,{}}});
        const auto& s=observe();require(!s.camp_hit&&s.incoming==0,"inactive attacker has no threat");clear_calls();
        require(scan_move({7,5})==RouteStatus::no_route_now,"inactive attack range ignored");
        require(fake::field_blocked==s.blocked,"inactive attacker occupancy only");
        expect_calls({state?"LW":"L"});++cases;
    }
    std::cout<<"PASS: "<<cases<<" production observation/navigation scenarios and live-query traces\n";
}
