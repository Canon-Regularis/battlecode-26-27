#include "economic_route.h"
#include <algorithm>
#include <iostream>
#include <queue>
#include <stdexcept>
using namespace lp::economic;
unsigned checks=0;
#define CHECK(...) do{++checks;if(!(__VA_ARGS__))throw std::runtime_error("line "+std::to_string(__LINE__)+": " #__VA_ARGS__);}while(0)
// Independent test geometry oracle. Production uses native full-origin fields.
Field field(Point origin,int w=9,int h=9,std::vector<Point> blocks={}) {
    Field f;f.width=w;f.height=h;f.origin=origin;f.epoch={1,0,1,1};f.complete=true;f.graph=1;
    f.blocked.assign(w*h,0);f.covered.assign(w*h,1);f.distances.assign(w*h,65535);
    for(auto p:blocks)f.blocked[p.y*w+p.x]=1;
    std::queue<Point> q;q.push(origin);f.distances[origin.y*w+origin.x]=0;
    while(!q.empty()){auto p=q.front();q.pop();for(int dy=-1;dy<=1;++dy)for(int dx=-1;dx<=1;++dx) {
        Point n{p.x+dx,p.y+dy};if(n.x<0||n.y<0||n.x>=w||n.y>=h)continue;int cell=n.y*w+n.x;
        if(f.blocked[cell]||f.distances[cell]!=65535)continue;
        f.distances[cell]=f.distances[p.y*w+p.x]+1;q.push(n);
    }}return f;
}
Key key(int id=1){return {id,0,0,Purpose::gems,Role::worker};}
RouteResult complete(Route& route,Point origin,int round=1) {
    RouteResult result;
    for(int n=0;n<8;++n){unsigned writes=0;result=route.continue_plan({1,0,round+n,1},origin,writes);
        CHECK(writes<=4096);if(result.status!=Travel::planning)return result;}
    return result;
}
void retained_and_repair() {
    Route route;auto f=field({0,0});auto k=key();
    CHECK(route.start(f,k,{{8,8}},false).status==Travel::planning);
    auto result=complete(route,{0,0});CHECK(result.status==Travel::ready&&result.next==Point{1,1});
    auto before=route.accepted_path();CHECK(before.size()==9);
    CHECK(route.motion(1,k,{0,0},{1,1},true,true,false));
    CHECK(route.position()==1);
    // A fresh field offers a shorter goal; it cannot replace accepted intent
    // until explicitly requested repair. The retained next edge remains (2,2).
    CHECK(route.next(k,{1,1}).next==Point{2,2});
    auto repair=field({1,1},9,9,{{2,2},{3,3}});
    CHECK(route.start(repair,k,{{8,8}},true).status==Travel::planning);
    result=complete(route,{1,1},2);CHECK(result.status==Travel::ready);
    auto path=route.accepted_path();CHECK(path.back()==80);
    // Earliest reachable anchor is index4 (4,4); its suffix (5,5)..(8,8) survives.
    auto anchor=std::find(path.begin(),path.end(),40);CHECK(anchor!=path.end());
    CHECK(std::vector<std::uint16_t>(anchor,path.end())==std::vector<std::uint16_t>({40,50,60,70,80}));
    CHECK(route.position()==0); // repair earns no achieved waypoint
}
void failures_and_reentry() {
    Route route;auto k=key();CHECK(route.start(field({0,0}),k,{{8,8}},false).status==Travel::planning);
    complete(route,{0,0});auto before=route.accepted_path();
    CHECK(!route.motion(1,k,{0,0},{1,1},false,true,true));CHECK(route.position()==0);
    CHECK(!route.motion(1,k,{0,0},{1,1},false,true,true));
    CHECK(!route.motion(2,k,{0,0},{1,1},false,true,true));
    CHECK(route.finish_execution(k,1,false,false).status==Travel::exhausted);
    CHECK(route.finish_execution(k,1,false,false).reason==RouteFailure::contact);
    CHECK(route.start(field({0,0}),k,{{8,8}},false).status==Travel::exhausted);
    CHECK(route.reopen(k,Reason::occupied,42));CHECK(!route.reopen(k,Reason::occupied,42));
    CHECK(route.start(field({0,0}),k,{{8,8}},true).status==Travel::planning);
    CHECK(complete(route,{0,0},2).status==Travel::ready);
    CHECK(route.accepted_path()==before);
    // Accepted action returning stale records physical acceptance elsewhere,
    // but must not advance this route cursor or invent its terminal arrival.
    CHECK(!route.motion(3,k,{0,0},{1,1},true,false,false));CHECK(route.position()==0);
}
void bounds_and_publication() {
    Route route;auto f=field({0,0});f.distances[80]=20;
    CHECK(route.start(f,key(),{{8,8}},false).status==Travel::planning);
    CHECK(complete(route,{0,0}).status==Travel::exhausted);
    CHECK(route.accepted_path().empty());
    Route malformed;auto bad=field({0,0});bad.complete=false;
    CHECK(malformed.start(bad,key(),{{8,8}},false).reason==RouteFailure::invalid_field);
    Route stale;CHECK(stale.start(field({0,0}),key(),{{8,8}},false).status==Travel::planning);
    unsigned writes=0;CHECK(stale.continue_plan({1,1,2,1},{0,0},writes).status==Travel::stale);
    CHECK(stale.accepted_path().empty());
    Route longroute;auto large=field({0,0},128,128); // full supported 16,384-cell field
    CHECK(longroute.start(large,key(),{{127,127}},false).status==Travel::planning);
    writes=4095;CHECK(longroute.continue_plan({1,0,1,1},{0,0},writes).status==Travel::planning&&writes==4096);
    CHECK(longroute.accepted_path().empty());CHECK(complete(longroute,{0,0},2).status==Travel::ready);
    CHECK(longroute.accepted_path().size()==128);
    Route conditional;auto unknown=field({0,0});unknown.covered[10]=0;
    conditional.start(unknown,key(),{{8,8}},false);CHECK(complete(conditional,{0,0}).conditional);
    Route stalled;auto k=key();stalled.start(field({0,0}),k,{{8,8}},false);complete(stalled,{0,0});
    for(int r=1;r<8;++r)CHECK(stalled.finish_execution(k,r,true,false).status==Travel::ready);
    CHECK(stalled.finish_execution(k,8,true,false).status==Travel::exhausted);
    Route lives;
    for(int life=0;life<3;++life) {
        auto f=field({0,0});f.epoch.life=life;
        CHECK(lives.start(std::move(f),k,{{8,8}},false).status==Travel::planning);
        unsigned count=0;CHECK(lives.continue_plan({1,life,1,1},{0,0},count).status==Travel::ready);
        lives.invalidate_life();CHECK(lives.accepted_path().empty()&&!lives.retains(k));
    }
    auto newlife=field({0,0});newlife.epoch.life=3;
    CHECK(lives.start(std::move(newlife),k,{{8,8}},false).status==Travel::exhausted);
}
int main(){try{retained_and_repair();failures_and_reentry();bounds_and_publication();
    std::cout<<"PASS: "<<checks<<" retained-economic-route assertions (synthetic oracle fields)\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
