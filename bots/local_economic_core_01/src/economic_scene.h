#pragma once
#include "economic_owner.h"
#include <array>
namespace lp::economic {
enum class AbilityKind { none, reset, damage, cc, dash, shield, heal, unsupported };
struct Ability {
    AbilityKind kind=AbilityKind::none;
    int slot=-1,range=0,radius=0,cooldown=0;
    float amount=0;
    bool supported=false,exclusive=false,camps=false,enemies=false,allies=false,self=false,
        ground=false,damaging=false,stunning=false;
};
struct Member {
    unsigned key=0;
    int group=-1,range=0;
    Point pos;
    float hp=0,strength=0,prior_hp=0;
    bool visible=false,known=false,alive=false,awake=false,passive=false,hp_known=false;
    action::Epoch hp_epoch,state_epoch;
    std::uint64_t unchanged_event=0;
};
struct Champion {
    int key=0,range=0,timer=0,move_range=0;
    Point pos;
    float hp=0,max_hp=1,strength=0;
    bool alive=false,channel=false,departing=false;
};
struct Group {
    GroupObservation observation;
    Point anchor;
    std::uint64_t gems=0,gold=0;
    std::vector<Point> spawn;
};
struct Lock {Point pos;bool allied=false;unsigned hits=0;};
struct Scene {
    Observation economy;
    int width=0,height=0,attack_range=0,move_range=0;
    float basic=0;
    bool can_move=false,can_attack=false,can_cast=false,move_restricted=false,
        attack_restricted=false,cast_restricted=false,consumable_restricted=false,
        ward_restricted=false,ranged=false;
    std::array<Ability,2> abilities{};
    std::vector<Member> members;
    std::vector<Group> groups;
    std::vector<Champion> enemies,allies;
    std::vector<Lock> locks;
    std::vector<Point> altars;
    unsigned carried_locks=0;
    // 7x7 centered at the actual origin. Outside is UNKNOWN, never safe/free.
    std::array<unsigned char,49> visible{},occupied{},blocked{};
    bool inside(Point p)const{return p.x>=0&&p.y>=0&&p.x<width&&p.y<height;}
    int local(Point p)const {
        int x=p.x-economy.self.pos.x+3,y=p.y-economy.self.pos.y+3;
        return x<0||y<0||x>=7||y>=7?-1:y*7+x;
    }
    bool seen(Point p)const{int i=local(p);return inside(p)&&i>=0&&visible[i];}
    bool physical(Point p)const {
        int i=local(p);return inside(p)&&i>=0&&visible[i]&&!blocked[i]&&
            (!occupied[i]||p==economy.self.pos);
    }
};
}
