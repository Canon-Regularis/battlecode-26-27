#pragma once
#include "config.h"
#include <cstdint>
// V2: normalize all short timestamps against the full frame clock before reading
// or updating. Expire records before advancing across a long scheduling gap.
namespace lp::party {
constexpr unsigned anchor=0,leader=6,message=9,chunk=12,type=18,owner=20;
constexpr unsigned created=23,refreshed=27,safety=29,enemy_chunk=41,enemy_count=47;
constexpr unsigned enemy_seen=50,clock=52,version=63;
constexpr std::uint64_t mask(unsigned n){return (std::uint64_t{1}<<n)-1;}
constexpr unsigned get(std::uint64_t w,unsigned b,unsigned n){return unsigned((w>>b)&mask(n));}
constexpr std::uint64_t put(std::uint64_t w,unsigned b,unsigned n,unsigned v){return (w&~(mask(n)<<b))|((std::uint64_t(v)&mask(n))<<b);}
constexpr int frame(std::uint64_t w){return int(get(w,clock,11));}
constexpr std::uint64_t empty(int r=0){
    auto w=put(0,anchor,6,63);w=put(w,leader,3,7);w=put(w,chunk,6,63);
    w=put(w,owner,3,7);w=put(w,safety,12,4095);w=put(w,enemy_chunk,6,63);
    w=put(w,clock,11,r);return put(w,version,1,1);
}
constexpr bool valid(std::uint64_t w,int r){
    return r>=0&&r<=2000&&get(w,version,1)==1&&frame(w)<=r&&frame(w)<=2000&&
        get(w,leader,3)!=6&&get(w,type,2)!=3;
}
constexpr int born(std::uint64_t w){return frame(w)-((frame(w)-int(get(w,created,4)))&15);}
constexpr int refresh_age(std::uint64_t w){return (frame(w)-int(get(w,refreshed,2)))&3;}
constexpr std::uint64_t clear(std::uint64_t w){return put(put(put(w,type,2,0),chunk,6,63),owner,3,7);}
constexpr std::uint64_t advance(std::uint64_t w,int r){
    if(!valid(w,r))return 0;
    int elapsed=r-frame(w);
    if(get(w,type,2)&&(born(w)<0||r-born(w)>=Config::rally_life||refresh_age(w)+elapsed>Config::rally_freshness))w=clear(w);
    if(get(w,enemy_count,3)&&(((frame(w)-int(get(w,enemy_seen,2)))&3)+elapsed>3)){
        w=put(w,enemy_count,3,0);w=put(w,enemy_chunk,6,63);
    }
    return put(w,clock,11,r);
}
constexpr bool live(std::uint64_t w,int r,int slots,int chunks){
    w=advance(w,r);
    return w&&get(w,type,2)>0&&get(w,owner,3)<unsigned(slots)&&get(w,chunk,6)<unsigned(chunks);
}
constexpr bool same(std::uint64_t a,std::uint64_t b){
    return get(a,type,2)>0&&get(b,type,2)>0&&get(a,owner,3)==get(b,owner,3)&&born(a)==born(b);
}
constexpr std::uint64_t create(std::uint64_t w,int slot,int r,int kind,int target){
    w=put(w,clock,11,r);w=put(w,owner,3,slot);w=put(w,created,4,unsigned(r)&15);
    w=put(w,refreshed,2,unsigned(r)&3);w=put(w,type,2,kind);return put(w,chunk,6,target);
}
constexpr std::uint64_t refresh(std::uint64_t w){return put(w,refreshed,2,unsigned(frame(w))&3);}
constexpr bool leader_live(std::uint64_t w,int r,int slots){
    return valid(w,r)&&get(w,leader,3)<unsigned(slots);
}
constexpr bool may_create(std::uint64_t w,int r,int kind,int last_created){
    w=advance(w,r);if(!w||r==last_created||kind<1||kind>2)return false;
    auto old=get(w,type,2);return old==0||(kind==1&&old==2);
}
constexpr std::uint64_t sighting(std::uint64_t w,int r,int target,int count){
    w=advance(w,r);if(!w||count<=0||target<0||target>=49)return w;
    auto old=get(w,enemy_count,3);
    if(!old||unsigned(count)>old||(get(w,enemy_chunk,6)==unsigned(target)&&unsigned(count)>=old)){
        w=put(w,enemy_chunk,6,target);w=put(w,enemy_count,3,count>7?7:count);w=put(w,enemy_seen,2,unsigned(r)&3);
    }
    return w;
}
}
