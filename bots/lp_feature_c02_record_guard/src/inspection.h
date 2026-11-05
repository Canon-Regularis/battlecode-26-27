#pragma once
#include "objectives.h"
#include "chunk_geometry.h"
namespace lp {
// Private incremental search context. The caller resolves identities/objectives.
// The cache contains legal candidates, not assertions about target presence.
struct Inspector {
    struct Candidate {vec2 p;int cover=0;};
    int target=-1,cursor=0,phase=0,ticks=0,steps=0,views=0,stalled=0,retry=-1;
    int last_round=-1;std::uint64_t identity=0;
    std::vector<Candidate> cache;
    bitboard visited;
    vec2 viewpoint{-1,-1};
    void reset(int chunk,std::uint64_t key);
    InspectionResult step(World&,TurnBudget&,Memory&,int chunk,std::uint64_t key,int max_distance=65534);
};
}
