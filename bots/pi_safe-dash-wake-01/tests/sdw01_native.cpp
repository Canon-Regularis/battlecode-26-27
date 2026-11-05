#include "navigation.h"
#include "camp_topology_access.h"
#include "dash_witness.h"
#include <cassert>
#include <iostream>
namespace lp {
Snapshot snapshot;
const Snapshot& observe(){return snapshot;}
void invalidate_observations(){}
bool move_checked(vec2 p){if(fail_moves){--fail_moves;return false;}assert(p==ordinary);++actions;++moves;return true;}
float incoming_at(vec2,const std::vector<champion>&){return 0;}
}
using namespace lp;
World world;
void reset(){epoch=1;fuel=100000;round_queries=fuel_queries=0;queries=trip=fields=actions=dashes=moves=fail_moves=0;trip_fuel=-1;trace.clear();camp_data.clear();world.camps.clear();dash={};actor_focus=233;actor_hp=1000;actor_shield=0;actor.identity=0;snapshot={};origin={10,10};endpoint={12,12};ordinary={11,10};reached_field=true;field_fuel=20000;}
void group(std::initializer_list<int> ids){Objective o;for(int i:ids)o.group.storage.push_back({i});world.camps.push_back(std::move(o));}
void member(int i,vec2 p,float strength=60,int range=4,bool awake=false,bool visible=true){camp_data[i]={i,p,awake,true,visible,strength,range};}
RouteStatus run(bool safe=true,bool constrained=false,bool retreat_call=false){snapshot.pos=origin;Memory m;TurnBudget b{epoch};bitboard goals;goals.set(endpoint);if(retreat_call)return retreat(b,m,CampTopologyView{world})?RouteStatus::moved:RouteStatus::deferred;auto result=move_to(goals,safe,b,m,CampTopologyView{world},constrained);if(result==RouteStatus::moved){assert(m.blocked==0);assert(m.last_distance==(dashes?1:9));}return result;}
void synthetic(){reset();group({1,2,3});member(10,{40,40},20,3,true);member(1,endpoint,0);member(2,{14,12});member(3,{14,13},60,4,false,false);}
int main(){
 // Frozen case rows are read from the candidate's text fixture, not a copied predicate.
 int n;std::cin>>n;
 for(int k=0;k<n;++k){reset();int round,expected,count;std::cin>>round>>expected>>origin.x>>origin.y>>endpoint.x>>endpoint.y>>ordinary.x>>ordinary.y>>actor.identity>>actor_focus>>actor_hp>>actor_shield>>count;
  for(int j=0;j<count;++j){int id,g,x,y,awake,strength,range;std::cin>>id>>g>>x>>y>>awake>>strength>>range;member(id,{x,y},strength,range,awake);}
  int champions;std::cin>>champions;for(int j=0;j<champions;++j){int ally,id,x,y;std::cin>>ally>>id>>x>>y;(ally?snapshot.allies:snapshot.foes).push_back({id,{x,y}});}
  int groups;std::cin>>groups;for(int j=0;j<groups;++j){Objective o;int size;std::cin>>size;for(int t=0;t<size;++t){int id;std::cin>>id;o.group.storage.push_back({id});}world.camps.push_back(std::move(o));}
  epoch=round;assert(run()==RouteStatus::moved);assert(dashes==expected);assert(moves==1-expected);assert(fields==1);
  std::map<std::string,int> counts;for(auto& q:trace)++counts[q];
  std::cout<<round<<": dash="<<dashes<<" ordinary="<<moves<<" mock_data_queries="<<queries<<" round_queries="<<round_queries<<" fuel_queries="<<fuel_queries;for(auto& [name,count]:counts)std::cout<<" "<<name<<"="<<count;std::cout<<"\n";
 }
 synthetic();assert(run()==RouteStatus::moved&&moves==1);auto base_trace=trace;std::cout<<"synthetic query trace:";for(auto& q:trace)std::cout<<' '<<q;std::cout<<'\n';
 for(int mode=0;mode<9;++mode){synthetic();
  if(mode==0)for(auto& [i,d]:camp_data)d.awake=true;
  if(mode==1)for(auto& [i,d]:camp_data)d.strength=0;
  if(mode==2)camp_data[2].pos={17,12};
  if(mode==3){camp_data[1].pos={20,20};camp_data[2].pos={21,20};}
  if(mode==4)dash.modifier=0;
  if(mode==5)dash.duration=0;
  if(mode==8)camp_data[2].pos={13,12}; // directly stunned
  run(mode!=6,mode==7);assert(dashes==((mode==7||mode==0)?0:1));assert(actions==(mode==0?0:1));
 }
 synthetic();camp_data[2].visible=false;run();assert(dashes==1);
 synthetic();world.camps.clear();run();assert(moves==1);
 synthetic();actor_focus=0;field_fuel=14999;run();assert(dashes==1);
 // Awake/passive hit members still wake a sleeping sibling; range/radius boundaries.
 synthetic();camp_data[1].awake=true;run();assert(moves==1);
 synthetic();camp_data[2].range=2;run();assert(moves==1);
 synthetic();camp_data[2].range=1;run();assert(dashes==1);
 synthetic();world.camps.clear();std::vector<VisibleCamp> visible;bitboard blocked;TurnBudget b{1};assert(capture_camps(visible,blocked,b,true));assert(dash_witness(ability{},endpoint,visible,CampTopologyView{world},b)==DashCheck::incomplete);
 synthetic();world.camps.clear();camp_data[1].pos={20,20};camp_data[2].pos={21,20};run();assert(dashes==1);
 synthetic();auto view=CampTopologyView{world};auto copy=view;
 static_assert(sizeof(CampTopologyView)==sizeof(void*));
 assert(view.members(1)->identity()==world.camps[0].group.camps().data());
 assert(copy.members(2)->identity()==view.members(1)->identity());
 assert(!view.members(999));
 // No loader exists in the host shim. Repeated hit identities and a second group.
 synthetic();camp_data[2].strength=0;member(4,{12,13},0);world.camps[0].group.storage.push_back({4});group({5,6});member(5,{11,12},0);member(6,{9,12});run();assert(moves==1);
 // At every captured/query boundary, rollover or exhausted reserve suppresses all actions,
 // including retreat's emergency fallback. The field itself is allowed its original rules.
 int tested=0;
 for(bool retreat_call:{false,true})for(int low:{-1,4999})for(int q=1;q<=int(base_trace.size());++q){synthetic();trip=q;trip_fuel=low;run(true,false,retreat_call);assert(actions==0);assert(queries==q);if(q<10)assert(fields==0);++tested;}
 for(bool retreat_call:{false,true})for(int low:{5000,10000,14999})for(int q=10;q<=int(base_trace.size());++q){synthetic();trip=q;trip_fuel=low;run(true,false,retreat_call);assert(moves==1&&dashes==0);assert(queries==q);}
 // Diagnostic statuses remain distinct; these supplement public movement tests.
 synthetic();std::vector<VisibleCamp> vc;bitboard mask;TurnBudget diagnostic{1};
 assert(capture_camps(vc,mask,diagnostic,true));fuel=14999;
 assert(dash_witness(ability{},endpoint,vc,CampTopologyView{world},diagnostic)==DashCheck::resource);
 fuel=15000;assert(dash_witness(ability{},endpoint,vc,CampTopologyView{world},diagnostic)==DashCheck::witness);
 fuel=4999;assert(dash_witness(ability{},endpoint,vc,CampTopologyView{world},diagnostic)==DashCheck::deferred);
 std::cout<<"admission: 14999=resource fallback; 15000=witness; 4999=deferred\n";
 // Admission after the field, and current below-reserve return through retreat.
 synthetic();field_fuel=14999;run();assert(moves==1&&dashes==0);
 synthetic();field_fuel=4999;run(true,false,true);assert(actions==0);
 synthetic();field_fuel=15000;run();assert(moves==1);
 synthetic();trip=1;trip_fuel=4999;run(true,false,true);assert(actions==0);
 // Ordinary failure retries through constrained move_to with the same borrowed topology.
 synthetic();field_fuel=40000;fail_moves=1;run();assert(moves==1&&dashes==0&&fields==2);
 synthetic();field_fuel=40000;fail_moves=2;run();assert(moves==1&&dashes==0&&fields==3);
 synthetic();reached_field=false;run();assert(actions==0);
 std::cout<<"PASS: controls, topology, hidden queries, retry and "<<tested<<" resource/epoch injections, 18 current resource fallbacks\n";
}
