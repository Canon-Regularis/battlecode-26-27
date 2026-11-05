#pragma once
#include <algorithm>
#include <cstdint>
#include <vector>

namespace lp {
// Input order is World's canonical anchor order. Inspect public static metadata only.
template<class Camps>
int find_dominant_gem_camp(const Camps& camps) {
    std::int64_t total=0;
    for(const auto& o:camps)total+=std::int64_t(o.group.gem_value());
    for(int i=0;i<int(camps.size());++i) {
        const auto& group=camps[i].group;
        const std::int64_t gems=group.gem_value();
        if(gems<=0||group.gold_value()!=0||gems<=total-gems)continue;
        const auto members=group.camps();
        if(std::all_of(members.begin(),members.end(),[](const auto& c){return c.is_gem_cluster();}))return i;
    }
    return -1;
}

inline int bootstrap_gem_preference(int dominant,const std::vector<bool>& eligible,bool bootstrap) {
    return bootstrap&&dominant>=0&&dominant<int(eligible.size())&&eligible[dominant]?dominant:-1;
}
}
