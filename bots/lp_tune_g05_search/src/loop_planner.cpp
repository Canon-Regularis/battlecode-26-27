#include "loop_planner.h"
#include <algorithm>
#include <cstdint>
#include <unordered_map>

namespace subhan {
Evaluation evaluate(const Inputs& d,const Config& c,const std::vector<int>& route,int altar) {
    Evaluation e;if(route.empty())return e;
    int first=route.front(),last=route.back();
    if(d.spawn_distances[first]<0)return e;
    std::vector<int> legs{d.altar_distances[altar][first],d.altar_distances[altar][last]};
    for(std::size_t i=1;i<route.size();++i)legs.push_back(d.distances[route[i-1]][route[i]]);
    if(std::any_of(legs.begin(),legs.end(),[](int v){return v<0;}))return e;
    int floor=0;
    for(int i:route){const auto& g=d.camps[i];e.gems+=g.gems;e.gold+=g.gold;e.service+=g.service;floor=std::max(floor,g.respawn+g.service);}
    for(int n:legs)e.travel+=n;
    e.tribute=(e.gems+9)/10;e.active=e.travel+e.service+e.tribute;
    e.period=std::max(e.active,floor);e.first_deposit=e.active-legs[0]+d.spawn_distances[first];
    e.base_score=(e.gems+c.gold_weight*e.gold)/(e.period+c.opening_weight*e.first_deposit);
    if(!d.camp_risk.empty()) {
        double ar=d.altar_risk[altar];
        double exposure=legs[0]*(ar+d.camp_risk[first])/2+legs[1]*(ar+d.camp_risk[last])/2;
        for(std::size_t i=1;i<route.size();++i)exposure+=d.distances[route[i-1]][route[i]]*(d.camp_risk[route[i-1]]+d.camp_risk[route[i]])/2;
        for(int i:route)exposure+=d.camps[i].service*d.camp_risk[i];
        exposure+=(e.tribute+e.period-e.active)*ar;
        e.risk=std::clamp(exposure/e.period,0.,1.);
    }
    e.multiplier=1-(1-c.risk_tolerance)*e.risk;e.score=e.base_score*e.multiplier;e.valid=true;return e;
}

namespace {
std::uint64_t mask(const std::vector<int>& route){std::uint64_t m=0;for(int i:route)m|=std::uint64_t{1}<<i;return m;}
struct Candidates {
    std::vector<Loop> ordered;
    std::unordered_map<std::uint64_t,std::size_t> positions;
    void offer(Loop l) {
        auto key=mask(l.route)|(std::uint64_t(l.altar)<<56);auto [it,inserted]=positions.emplace(key,ordered.size());
        if(inserted)ordered.push_back(std::move(l));
        else if(l.evaluation.score>ordered[it->second].evaluation.score)ordered[it->second]=std::move(l);
    }
};
void rank(std::vector<Loop>& v){std::stable_sort(v.begin(),v.end(),[](const Loop& a,const Loop& b){return a.evaluation.score>b.evaluation.score;});}
}

std::vector<Loop> find_loops(const Inputs& d,const Config& c,const std::function<bool()>& stop) {
    // Preserve Python insertion order and stable ties. Hash tables are lookup-only.
    if(d.camps.size()>48||d.altar_distances.size()>255)return {};
    std::vector<std::vector<std::vector<int>>> beams(d.altar_distances.size(),{{}});
    Candidates finalists;
    int expansions=0;bool exhausted=false;
    for(int length=0;length<std::min(c.max_camps,int(d.camps.size()));++length) {
        std::vector<Candidates> candidates(beams.size());std::size_t largest=0;
        for(const auto& b:beams)largest=std::max(largest,b.size());
        for(std::size_t bi=0;bi<largest&&!exhausted;++bi)for(std::size_t ai=0;ai<beams.size()&&!exhausted;++ai) {
            if(bi>=beams[ai].size())continue;const auto& parent=beams[ai][bi];
            for(int camp=0;camp<int(d.camps.size())&&!exhausted;++camp) {
                if(std::find(parent.begin(),parent.end(),camp)!=parent.end())continue;
                for(std::size_t pos=0;pos<=parent.size();++pos) {
                    if(expansions>=c.max_expansions||(expansions%8==0&&stop())){exhausted=true;break;}
                    ++expansions;auto route=parent;route.insert(route.begin()+pos,camp);
                    auto e=evaluate(d,c,route,int(ai));if(e.valid)candidates[ai].offer({int(ai),std::move(route),e});
                }
            }
        }
        bool any=false;
        for(std::size_t ai=0;ai<beams.size();++ai) {
            auto& ranked=candidates[ai].ordered;rank(ranked);beams[ai].clear();
            for(int i=0;i<std::min(c.beam_width,int(ranked.size()));++i)beams[ai].push_back(ranked[i].route);
            for(int i=0;i<std::min(std::max(c.report_limit,c.beam_width),int(ranked.size()));++i)
                if(ranked[i].evaluation.gems)finalists.offer(ranked[i]);
            any|=!beams[ai].empty();
        }
        if(exhausted||!any)break;
    }
    auto result=std::move(finalists.ordered);
    rank(result);if(int(result.size())>c.report_limit)result.resize(c.report_limit);return result;
}
}
