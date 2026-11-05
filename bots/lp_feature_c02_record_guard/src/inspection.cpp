#include "feature_flags.h"
#if PARTY_FEATURE_MASK & ((1ULL<<3)|(1ULL<<4)|(1ULL<<5))
#include "inspection.h"
#include "strategy_policy.h"
#include <tuple>
namespace lp {
void Inspector::reset(int chunk,std::uint64_t key){
    target=chunk;identity=key;cursor=phase=ticks=steps=views=stalled=0;
    cache.clear();visited=bitboard{};viewpoint={-1,-1};retry=-1;last_round=-1;
}
InspectionResult Inspector::step(World& w,TurnBudget& b,Memory& m,int chunk,std::uint64_t key,int limit) {
    if(target!=chunk||identity!=key)reset(chunk,key);
    auto bounds=chunk_bounds(w.width,w.height,chunk);if(!bounds.valid())return InspectionResult::expired;
    const auto& s=observe();if(s.round<retry)return InspectionResult::defer;
    auto fail=[&](InspectionResult v){retry=s.round+Config::inspection_retry;ticks=steps=views=stalled=0;cursor=phase=0;cache.clear();viewpoint={-1,-1};return v;};
    bitboard region;for(int y=bounds.y0;y<=bounds.y1;++y)for(int x=bounds.x0;x<=bounds.x1;++x)region.set({x,y});
    if((region&~s.visible).is_empty())return fail(InspectionResult::no_match_now);
    if(last_round!=s.round){last_round=s.round;if(w.chunk(s.pos)==chunk||views>0)++ticks;}
    if(inspection_exhausted(ticks,steps,views))return fail(InspectionResult::exhausted);
    if(fuel_remaining()<Config::inspection_fuel||!b.current())return InspectionResult::defer;
    // At most 128 raw candidates and four exact SDK visibility calls per turn.
    // Bushes in chunk, other chunk tiles, then halo. No whole-map sorting.
    auto bushes=map::bushes();auto blocked=static_blocked();int queries=0,scanned=0;
    while(phase<3&&scanned<Config::inspection_scan&&queries<Config::inspection_queries&&fuel_remaining()>Config::inspection_fuel){
        auto candidate=next_inspection_candidate(bounds,w.width,w.height,phase,cursor);
        if(candidate.phase==3)break;
        ++scanned;vec2 p{candidate.x,candidate.y};
        bool inside=region.is_set(p),bush=bushes.is_set(p);
        if((phase==0&&(!inside||!bush))||(phase==1&&(!inside||bush))||(phase==2&&inside)||blocked.is_set(p)||visited.is_set(p))continue;
        auto visible=self().visible_tiles_from(p);++queries;
        int coverage=int((visible&region&~s.visible).positions().size());
        if(coverage>0){cache.push_back({p,coverage});if(cache.size()>Config::inspection_cache){auto worst=std::min_element(cache.begin(),cache.end(),[](auto a,auto c){return a.cover<c.cover;});cache.erase(worst);}}
    }
    if(!b.current())return InspectionResult::defer;
    if(viewpoint.x<0){
        if(cache.empty())return phase>=3?fail(InspectionResult::no_viewpoint):InspectionResult::defer;
        if(!b.admit())return InspectionResult::defer;
        distance_field f;bitboard reached;auto mask=s.blocked|s.risk;mask.set(s.pos,false);++b.fields;f.compute(mask,around(s.pos,0),reached,std::min(limit,65534));
        if(!b.current())return InspectionResult::defer;
        auto rank=std::tuple{100000,100000,100000,100000};
        for(auto c:cache)if(reached.is_set(c.p)&&f.get(c.p)<=limit){auto v=std::tuple{-c.cover,int(f.get(c.p)),c.p.y,c.p.x};if(v<rank){rank=v;viewpoint=c.p;}}
        if(viewpoint.x<0)return fail(InspectionResult::blocked);
    }
    auto from=s.pos;auto result=move_to(around(viewpoint,0),true,b,m,true);
    if(!b.current())return InspectionResult::defer;
    auto to=observe().pos;steps+=cheb(from,to);
    if(to==viewpoint){visited.set(viewpoint);++views;viewpoint={-1,-1};cache.clear();cursor=phase=0;stalled=0;return InspectionResult::contact;}
    if(result==RouteStatus::deferred)return InspectionResult::defer;
    if(to==from){if(++stalled>=Config::inspection_stall)return fail(InspectionResult::blocked);}else stalled=0;
    return InspectionResult::moving;
}
}

#endif
