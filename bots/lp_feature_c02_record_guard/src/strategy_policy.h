#pragma once
#include "config.h"
namespace lp {
constexpr bool leadership_admission(int round,int priority_round,float hp,float max_hp,bool recovery,bool escape){
    return round>priority_round&&hp>max_hp*0.5f&&!recovery&&!escape;
}
constexpr int maintain_leader(int current,bool dead,int slot,bool eligible){
    if(dead||(current==slot&&!eligible))current=7;
    return current==7&&eligible?slot:current;
}
constexpr bool rally_distance_allowed(int kind,int distance){
    return distance>=0&&distance<=(kind==1?Config::bank_response:kind==2?Config::attack_response:-1);
}
constexpr bool rally_admitted(bool accepted,int kind,int distance){
    return (accepted&&kind==2)||rally_distance_allowed(kind,distance);
}
constexpr bool bank_completed(int tracked,int tracked_life,int life,bool channel,int bag,int score_delta){
    return tracked>0&&tracked_life==life&&!channel&&bag==0&&score_delta>=tracked;
}
constexpr bool escort_valid(bool alive,bool visible,int bag,int distance,int missing){
    return alive&&(visible?(bag>0&&distance<=2):missing<=Config::bank_reacquire);
}
constexpr bool attack_admission(int visible,int enemies,int friends,int distance,float hp,float max_hp,float target_hp,float target_max){
    return visible==1&&enemies<=friends&&distance<=2&&hp>max_hp*Config::recovery_high&&target_hp<=target_max*0.5f&&hp>target_hp;
}
constexpr bool inspection_exhausted(int turns,int steps,int views){
    return turns>=Config::inspection_turns||steps>=Config::inspection_steps||views>=Config::inspection_views;
}
struct WardRank {int radius=-1,cross=0,dot=1;};
constexpr bool ward_forward(int dot,int cross){return dot>0&&cross<=dot;}
constexpr bool ward_better(WardRank a,WardRank b){
    return a.radius>b.radius||(a.radius==b.radius&&(a.cross*b.dot<b.cross*a.dot||(a.cross*b.dot==b.cross*a.dot&&a.dot>b.dot)));
}
}
