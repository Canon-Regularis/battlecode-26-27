#include "economic_access.h"
#include <algorithm>
#include <cmath>
namespace lp::economic {
namespace {
int distance(Point a,Point b){return std::max(std::abs(a.x-b.x),std::abs(a.y-b.y));}
std::uint64_t mix(std::uint64_t a,std::uint64_t b){return (a^b)*1099511628211ull;}
}
bool AccessQueue::wait(const Scene& s,unsigned index,int range) {
    const auto& own=s.economy.self;
    if(!s.economy.complete||!own.alive||own.completed||own.stunned||
        own.channel!=Channel::none||index>=s.altars.size()||range<0||range>3)return false;
    const auto altar=s.altars[index];
    if(distance(altar,own.pos)>range+1)return false;
    for(int dy=-range;dy<=range;++dy)for(int dx=-range;dx<=range;++dx) {
        const Point p{altar.x+dx,altar.y+dy};
        if(p==altar||!s.inside(p))continue;
        if(s.physical(p)){*this={};return false;}
        if(!s.seen(p))return false;
        if(s.blocked[s.local(p)])continue;
        // Unknown, hostile, camp or low-priority physical occupants do not
        // become a cooperative allied queue.
        bool ally=false;
        for(const auto& a:s.allies)if(a.alive&&a.pos==p&&
            (a.channel||a.bag>own.bag||(a.bag==own.bag&&a.bag>0&&a.key<own.epoch.actor)))ally=true;
        if(!ally)return false;
    }
    bool relevant=false,channel=false;
    std::uint64_t hash=1469598103934665603ull,total_timer=0;
    int largest_timer=0;unsigned total_approach=0;std::uint64_t current_hits=0;
    for(const auto& lock:s.locks)if(lock.pos==altar&&!lock.allied)current_hits+=lock.hits;
    // Capture's ally order is stable. Channel state is deliberately absent
    // from identity so one observed waiting-to-channel transition can promote.
    for(const auto& ally:s.allies)if(ally.alive&&distance(ally.pos,altar)<=range) {
        if(!ally.channel&&!(ally.bag>own.bag||(ally.bag==own.bag&&ally.bag>0&&ally.key<own.epoch.actor)))continue;
        relevant=true;hash=mix(hash,unsigned(ally.key));total_approach+=unsigned(distance(ally.pos,altar));
        if(ally.channel) {
            if(ally.timer<0)return false;
            channel=true;total_timer+=unsigned(ally.timer);largest_timer=std::max(largest_timer,ally.timer);
        }
    }
    if(!relevant||finished)return false;
    const int round=own.epoch.round;
    if(last_round==round)return true;
    if(!observed) {
        observed=true;blockers=hash;timers=total_timer;approach=total_approach;lock_hits=current_hits;last_round=round;eligible=1;
        promoted=channel;deadline=std::int64_t(round)+(channel?std::int64_t(largest_timer)+1:2);return true;
    }
    // Neither changed blockers nor channel restarts mint another deadline.
    if(blockers!=hash||round>deadline){finished=true;return false;}
    if(!promoted&&channel) {
        promoted=true;deadline=std::int64_t(round)+largest_timer+1;
    } else if(promoted&&(!channel||total_timer>=timers)) {
        finished=true;return false;
    } else if(!channel&&(eligible>=3||!(total_approach<approach||current_hits<lock_hits))) {
        finished=true;return false;
    }
    timers=total_timer;approach=total_approach;lock_hits=current_hits;last_round=round;++eligible;return true;
}
}
