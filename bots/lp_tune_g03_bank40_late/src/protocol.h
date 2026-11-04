#pragma once
#include "config.h"
#include <cstdint>
namespace lp::wire {
constexpr unsigned anchor=0,leader=6,message=9,chunk=12,type=18,owner=20,created=23,safety=34,heartbeat=46,initialized=57,version=58;
constexpr std::uint64_t mask(unsigned n) { return (std::uint64_t{1}<<n)-1; }
constexpr unsigned get(std::uint64_t w,unsigned b,unsigned n) {return unsigned((w>>b)&mask(n));}
constexpr std::uint64_t put(std::uint64_t w,unsigned b,unsigned n,unsigned v) {return (w&~(mask(n)<<b))|((std::uint64_t(v)&mask(n))<<b);}
constexpr std::uint64_t empty() {
    auto w=put(0,anchor,6,63);w=put(w,leader,3,7);w=put(w,chunk,6,63);
    w=put(w,owner,3,7);w=put(w,safety,12,4095);w=put(w,initialized,1,1);return put(w,version,3,1);
}
constexpr bool valid(std::uint64_t w,int r) {return r>=0&&r<=2000&&get(w,initialized,1)&&get(w,version,3)==1&&get(w,leader,3)!=6&&get(w,type,2)!=3;}
constexpr std::uint64_t identity(std::uint64_t w) {return w&((mask(3)<<owner)|(mask(11)<<created));}
constexpr bool live(std::uint64_t w,int r,int slots,int chunks) {
    return valid(w,r)&&get(w,type,2)>0&&get(w,owner,3)<unsigned(slots)&&get(w,chunk,6)<unsigned(chunks)&&
        int(get(w,created,11))<=r&&r-int(get(w,created,11))<Config::rally_life;
}
constexpr bool same(std::uint64_t a,std::uint64_t b) {return identity(a)==identity(b)&&get(a,type,2)&&get(b,type,2);}
constexpr std::uint64_t clear(std::uint64_t w) {return put(put(put(w,type,2,0),chunk,6,63),owner,3,7);}
constexpr std::uint64_t create(std::uint64_t w,int slot,int r,int kind,int target) {
    return put(put(put(put(w,owner,3,slot),created,11,r),type,2,kind),chunk,6,target);
}
constexpr bool leader_live(std::uint64_t w,int r,int n) {
    return valid(w,r)&&get(w,leader,3)<unsigned(n)&&int(get(w,heartbeat,11))<=r&&r-int(get(w,heartbeat,11))<=Config::lease;
}
}
