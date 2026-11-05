#pragma once
#include <algorithm>
#include <cstdint>
#include <optional>
#include <vector>
namespace lp::occupancy {
struct Position {int x=0,y=0;bool operator==(const Position&) const = default;};
struct Key {int life=0,task=-1,started=0;bool operator==(const Key&) const = default;};
struct Positive {int identity;Position position;};
struct Batch {
    int round=0;unsigned revision=0;bool complete=false;int width=100,height=100;
    std::vector<Positive> positives;
    std::vector<Position> visible;
};
struct Token {
    int identity,round;unsigned observation;std::uint64_t version;Position position;
    bool operator==(const Token&) const = default;
};
struct Attempt {std::uint64_t scope=0;int round=0;unsigned observation=0;bool current=false;std::vector<Token> uncertain;};
enum class Outcome {other,no_route,overlay_empty};
class Cache {
    struct Entry {int identity;std::optional<Token> record;int alive_round=-1;std::optional<Token> pending;int failed_round=-1;};
    std::vector<Entry> entries;
    Key key;int self=-1;std::uint64_t scope=0,serial=0;
public:
    void configure(const std::vector<int>& roster,int own) {
        if(self==own&&!entries.empty())return;
        self=own;entries.clear();for(int i:roster)if(i!=own)entries.push_back({i,{},-1,{},-1});
    }
    void reset(Key next) {if(next==key)return;key=next;++scope;for(auto& e:entries){e.record.reset();e.pending.reset();e.alive_round=-1;}}
    // All mutation is staged until the complete owned batch and bounded guards agree.
    // alive(identity) returns unknown on expected query failure; never queries position.
    template<class Current,class Alive>
    Attempt prepare(const Batch& b,bool normal_attempt,Current current,Alive alive) {
        Attempt a{scope,b.round,b.revision,false,{}};
        if(key.task<0||!b.complete||b.round<0||!current())return a;
        auto staged=entries;
        for(auto& e:staged) {
            auto p=std::find_if(b.positives.begin(),b.positives.end(),[&](auto& v){return v.identity==e.identity;});
            if(p!=b.positives.end()) {
                if(p->position.x<0||p->position.y<0||p->position.x>=b.width||p->position.y>=b.height)continue;
                if(!e.record||e.record->round!=b.round||e.record->observation!=b.revision||e.record->position!=p->position)
                    e.record=Token{e.identity,b.round,b.revision,++serial,p->position};
                e.alive_round=b.round;e.pending.reset();
            } else if(e.record) {
                if(std::find(b.visible.begin(),b.visible.end(),e.record->position)!=b.visible.end()) {e.record.reset();e.pending.reset();continue;}
                if(e.alive_round!=b.round) {
                    for(auto& original:entries)if(original.identity==e.identity)original.alive_round=b.round;
                    e.alive_round=b.round;
                    auto live=alive(e.identity);
                    if(live&&!*live){e.record.reset();e.pending.reset();continue;}
                }
                if(normal_attempt&&e.pending&&b.round>e.failed_round&&e.record==e.pending){e.record.reset();e.pending.reset();continue;}
                a.uncertain.push_back(*e.record);
            }
        }
        if(!current())return Attempt{scope,b.round,b.revision,false,{}};
        entries=std::move(staged);a.current=true;return a;
    }
    void feedback(const Attempt& a,Outcome outcome,int round,unsigned observation,bool complete) {
        if(!complete||!a.current||a.scope!=scope||round!=a.round||observation!=a.observation||outcome==Outcome::other)return;
        for(auto& e:entries)if(e.record&&std::find(a.uncertain.begin(),a.uncertain.end(),*e.record)!=a.uncertain.end()) {
            e.pending=e.record;e.failed_round=round;
        }
    }
};
}
