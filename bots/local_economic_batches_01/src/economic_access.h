#pragma once
#include "economic_scene.h"
namespace lp::economic {
// A finite physical-access wait, not an engine per-altar queue. The caller
// certifies current safety. Only an observed free stand resets the episode.
class AccessQueue {
    std::uint64_t blockers=0,timers=0,lock_hits=0;
    unsigned approach=0;
    std::int64_t deadline=-1;
    int last_round=-1;
    unsigned eligible=0;
    bool observed=false,promoted=false,finished=false;
public:
    bool wait(const Scene&,unsigned altar,int submit_range);
};
}
