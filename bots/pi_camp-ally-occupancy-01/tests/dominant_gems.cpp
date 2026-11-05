// Native policy harness: real metadata helper and extracted production selection body.
// Distance results and SDK metadata are deterministic fixtures, not an engine simulation.
#include "dominant_gems.h"
#include "config.h"
#include <cmath>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <tuple>
#include <vector>
namespace lp {
struct vec2 {int x=0,y=0;};
int cheb(vec2 a,vec2 b){return std::max(std::abs(a.x-b.x),std::abs(a.y-b.y));}
struct bitboard {
    std::vector<vec2> points;
    void set(vec2,bool){}
    auto positions()const{return points;}
};
bitboard operator|(bitboard a,bitboard){return a;}
bitboard around(vec2 p,int){return {{p}};}
std::vector<unsigned short> field_distances;
struct distance_field {
    void compute(bitboard,bitboard,bitboard&){}
    auto export_linear_buffer(){return field_distances;}
};
enum class Kind {gem_cluster,gold_cluster,wolf,elk,monolith,golem};
struct Camp {Kind kind=Kind::gem_cluster;bool is_gem_cluster()const{return kind==Kind::gem_cluster;}};
struct Group {
    std::uint32_t gems=0,gold=0;
    std::vector<Camp> members{{}};
    auto gem_value()const{return gems;}
    auto gold_value()const{return gold;}
    auto camps()const{return members;}
};
struct Objective {
    Group group;
    vec2 anchor;
    bitboard approach;
    int cooldown=0,lifecycle=0,respawn=0,seen=-1;
    float remaining=0,design_health=10;
};
struct World {
    std::vector<Objective> camps;
    std::vector<vec2> altars;
    int width=8,dominant_gem_camp=-1;
};
struct Actor {
    int identity=0;
    float power=10;
    float strength()const{return power;}
    float focus()const{return 0;}
    vec2 position()const{return {};}
};
Actor actor;
Actor& self(){return actor;}
int id(const Actor& a){return a.identity;}
struct Snapshot {bitboard blocked,risk;vec2 pos;int round=100;std::vector<Actor> allies;};
struct TurnBudget {bool admitted=true,current_round=true;int fields=0;bool admit(){return admitted;}bool current(){return current_round;}};
int planned=-1,planner_calls=0;
int preferred_loop_camp(World&,const std::vector<bool>& eligible){++planner_calls;return planned>=0&&eligible[planned]?planned:-1;}
#include "choose-camp-under-test.h"
void initialize_metadata(World& w) {
    auto& camps=w.camps;
    auto& dominant_gem_camp=w.dominant_gem_camp;
#include "canonical-metadata-under-test.h"
}
}
using namespace lp;
int checks=0;
void require(bool ok,const char* name){++checks;if(!ok){std::cerr<<"FAIL: "<<name<<'\n';std::exit(1);}}
World fixture() {
    World w;
    // Incoming order differs from canonical y/x order; IDs are irrelevant.
    Objective dominant;dominant.group.gems=100;dominant.anchor={3,2};dominant.approach.points={{3,0}};
    Objective ordinary;ordinary.group.gems=10;ordinary.anchor={1,1};ordinary.approach.points={{1,0}};
    w.camps={dominant,ordinary};initialize_metadata(w);
    field_distances.assign(8,65535);field_distances[1]=1;field_distances[3]=20;
    planned=-1;planner_calls=0;actor.power=10;
    return w;
}
int select(World& w,bool bootstrap=true,bool distance=true) {Snapshot s;TurnBudget b;return choose_camp(w,s,b,distance,bootstrap);}
int main() {
    World w=fixture();
    require(w.dominant_gem_camp==1&&w.camps[1].group.gems==100,"canonical index after actual anchor sort");
    require(select(w)==1&&planner_calls==0,"bootstrap prefers eligible dominant over nearer fallback");
    require(select(w,true,false)==1,"bootstrap preference also applies outside distance mode");
    require(select(w,false)==0,"later phase keeps ordinary distance fallback");
    planned=0;require(select(w,false)==0&&planner_calls==2,"later phase planner retains precedence");
    planned=1;require(select(w,false)==1,"later phase retains its planned choice");
    w.dominant_gem_camp=-1;require(select(w)==0,"absent dominant preserves fallback");
    w=fixture();w.camps[1].design_health=5880;w.camps[1].cooldown=101;require(select(w)==0,"retry cooldown preserves fallback");
    w.camps[1].cooldown=100;require(select(w)==1,"cooldown expires at current round");
    field_distances[3]=65535;require(select(w)==0,"blocked or risky unreachable approach preserves fallback");
    w=fixture();w.camps[1].design_health=5880;w.camps[1].lifecycle=3;w.camps[1].respawn=121;
    require(select(w)==0,"respawn after arrival preserves fallback");
    w.camps[1].respawn=120;require(select(w)==1,"respawn by arrival remains eligible");
    w=fixture();w.camps[1].design_health=901;
    require(select(w)==1,"overlong dominant admitted during bootstrap distance mode");
    require(select(w,true,false)==1,"overlong dominant admitted during bootstrap value mode");
    require(select(w,false)==0,"overlong dominant rejected after bootstrap");
    planned=1;require(select(w,false)==0,"later planner cannot bypass dominant clear gate");
    require(select(w,false,false)==0,"later value fallback preserves dominant clear gate");
    w.camps[1].design_health=5880;w.camps[1].group.members.assign(49,{});
    initialize_metadata(w);
    require(select(w)==1,"large multi-cluster passive objective admitted during bootstrap");
    require(select(w,false)==0,"large multi-cluster passive objective rejected later");
    w.camps[1].design_health=900;require(select(w)==1,"estimated clear exactly 90 remains eligible");
    w.camps[1].design_health=10000;w.camps[1].lifecycle=1;w.camps[1].seen=100;w.camps[1].remaining=660;
    require(select(w)==1,"visible remaining health can admit dominant");
    w.camps[1].seen=99;require(select(w)==1,"stale overlong dominant admitted during bootstrap");
    require(select(w,false)==0,"later stale health retains conservative design estimate");
    w.camps[1].lifecycle=2;require(select(w)==1,"reward available retains existing zero-clear admission");
    w=fixture();w.camps[0].cooldown=w.camps[1].cooldown=101;require(select(w)==-1,"no eligible camps retains sentinel");
    w=fixture();w.camps[1].design_health=5880;Snapshot s;TurnBudget b;b.admitted=false;
    require(choose_camp(w,s,b,true,true)==-2,"budget admission still defers");
    b={};b.fields=1;require(choose_camp(w,s,b,true,true)==-2,"used field budget still defers");
    b={};b.current_round=false;require(choose_camp(w,s,b,true,true)==-2,"stale distance field still defers");

    // Exercise the production selector with a real recached metadata result.
    // The ordinary camp is gated even while the dominant exception is active.
    w=fixture();w.camps[1].cooldown=101;w.camps[0].design_health=901;
    require(select(w)==-1,"ordinary overlong camp rejected during bootstrap");
    require(select(w,false)==-1,"ordinary overlong camp rejected after bootstrap");
    w.camps[0].design_health=900;
    require(select(w)==0,"ordinary exactly-90 clear admitted during bootstrap");
    require(select(w,false)==0,"ordinary exactly-90 clear admitted after bootstrap");
    for(int variant=0;variant<8;++variant) {
        w=fixture();
        if(variant==0)w.camps[1].group.gems=10; // Equal reward.
        else if(variant==1)w.camps[1].group.gold=1;
        else {
            const Kind kinds[]={Kind::wolf,Kind::elk,Kind::monolith,Kind::golem,Kind::gold_cluster,Kind::wolf};
            w.camps[1].group.members={{kinds[variant-2]}};
            if(variant==7)w.camps[1].group.members.push_back({Kind::gem_cluster});
        }
        initialize_metadata(w);
        require(w.dominant_gem_camp==-1,"ineligible metadata has no admission exception");
        w.camps[1].design_health=901;
        require(select(w)==0,"equal/gold/attacking/mixed overlong group rejected at bootstrap");
        planned=1;
        require(select(w,false)==0,"equal/gold/attacking/mixed overlong group rejected later");
        w.camps[1].design_health=900;
        require(select(w,false)==1,"equal/gold/attacking/mixed exactly-90 group still eligible");
    }

    w=fixture();w.camps[1].group.gems=10;require(find_dominant_gem_camp(w.camps)==-1,"equal rewards are not strict dominance");
    w.camps[1].group.gems=0;w.camps[0].group.gems=0;require(find_dominant_gem_camp(w.camps)==-1,"zero reward cannot dominate");
    w=fixture();w.camps[1].group.gold=1;require(find_dominant_gem_camp(w.camps)==-1,"gold-bearing dominant excluded");
    for(auto kind:{Kind::wolf,Kind::elk,Kind::monolith,Kind::golem,Kind::gold_cluster}) {
        w=fixture();w.camps[1].group.members={{kind}};
        require(find_dominant_gem_camp(w.camps)==-1,"non-gem member excluded");
        w.camps[1].group.members.push_back({Kind::gem_cluster});
        require(find_dominant_gem_camp(w.camps)==-1,"mixed gem and non-gem group excluded");
    }
    w=fixture();w.camps[1].group.members.assign(49,{});
    require(find_dominant_gem_camp(w.camps)==1,"all passive gem members accepted");
    w.camps[0].group.gems=100;field_distances[1]=65535;
    require(find_dominant_gem_camp(w.camps)==-1,"unreachable groups still count in dominance total");
    w=fixture();w.camps[0].group.gems=60;auto third=w.camps[0];third.group.gems=40;w.camps.push_back(third);
    require(find_dominant_gem_camp(w.camps)==-1,"compare against sum of every other group");
    w.camps[2].group.gems=39;require(find_dominant_gem_camp(w.camps)==1,"strictly above other-group sum accepted");
    for(auto& o:w.camps)o.group.gems=std::numeric_limits<std::uint32_t>::max();
    require(find_dominant_gem_camp(w.camps)==-1,"64-bit total does not wrap at 32 bits");
    w.camps.resize(2);w.camps[0].group.gems=1;
    require(find_dominant_gem_camp(w.camps)==1,"full uint32 reward remains positive");
    w.camps.clear();require(find_dominant_gem_camp(w.camps)==-1,"empty map has no dominant");
    std::cout<<"PASS: "<<checks<<" dominant metadata / production selection checks\n";
}
