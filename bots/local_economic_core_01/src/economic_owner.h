#pragma once
// SDK-independent economic task ownership. Input records are owned scalar
// observations; neither SDK handles nor mutable Snapshot references cross here.
#include "turn_ledger.h"
#include <cstdint>
#include <vector>
namespace lp::economic {
struct Point {int x=0,y=0;friend bool operator==(Point,Point)=default;};
enum class Evidence { absent, deferred, unknown, unsupported, unavailable, impossible, ready, capacity };
enum class Purpose { gems, gold, convert, observe_access, recover };
enum class Role { worker, recipient, holder, takeover, defender, carrier };
enum class Phase { contact, service, hold, access, deliver, suspended, settled };
enum class Channel { none, recall, submit, teleport };
enum class Life { unknown, living, reward, respawning };
enum class Reason { none, allowance, cooldown, occupied, hidden, unsafe, no_effect,
    unsupported, role_satisfied, route, access, exhausted, capacity };
enum class Decision { task, protected_channel, recovery, healing, dead, deferred, no_task, capacity };
enum class Disposition { none, resources_changed, possible_deposit, loss, unknown };
enum class Stop { partial, work, holding, allowance, cooldown, blocked, unsupported,
    deferred, stale, exhausted, group_settled, channel_started, access_unavailable };
struct Resources {
    action::Epoch epoch;
    Point pos;
    float hp=0,max_hp=1;
    std::uint64_t bag=0,gold=0,score=0;
    bool alive=false,spawn=false,completed=false,stunned=false;
    Channel channel=Channel::none;
    int channel_timer=0;
    bool danger=false; // actual inherited danger predicate, not proposed wake
};
struct Key {
    int object=-1,cycle=-1,contact=-1;
    Purpose purpose=Purpose::gems;
    Role role=Role::worker;
    friend bool operator==(Key,Key)=default;
};
struct Task {
    Key key;
    Phase phase=Phase::contact;
    Point anchor;
    Evidence evidence=Evidence::unknown;
    Reason reason=Reason::none;
    bool present=false;
};
struct Rate {std::uint64_t value=0,time=1;bool priced=false;};
// compare returns -1/0/+1. No host calls, floating fallback or overflowing products.
int compare(Rate,Rate);
struct Candidate {
    Key key;
    Point anchor;
    Evidence approach=Evidence::unknown,service=Evidence::unknown,
        recipient=Evidence::unknown,conversion=Evidence::unknown;
    Reason blocker=Reason::none;
    std::uint64_t fact=0; // semantic blocker/support identity; never round/revision
    std::uint64_t approach_hops=0,work_turns=0,capture_turns=0,
        delivery_hops=0,tribute_turns=0,own_gems=0,own_gold=0;
    bool estimate_priced=false,conditional=true,winning_start=false;
};
struct GroupObservation {
    int object=-1,cycle=-1;
    Life life=Life::unknown;
    bool fresh=false,self_occupant=false,contested=false;
    bool allied_holder=false,holder_departing=false;
    int capture_timer=0,earliest_departure=0;
    // Positive lifecycle/occupancy evidence identity, not an observation epoch.
    std::uint64_t role_fact=0;
};
struct Observation {
    Resources self;
    std::vector<GroupObservation> groups;
    bool complete=false,has_altars=false;
};
struct Execution {
    // One completed owner dispatch/result, not a proposal or estimate correction.
    std::uint64_t event=0;
    Key key;
    Stop stop=Stop::partial;
    Reason reason=Reason::none;
    std::uint64_t fact=0;
    bool owned_bracket=false;
    float actual_damage=0;
    bool observed_gold_receipt=false,observed_gem_receipt=false;
};
struct Change {
    Key key;
    Reason addresses=Reason::none;
    std::uint64_t fact=0;
    bool positive=false; // positive clearance/new capability/new lifecycle only
};
struct Directive {
    Decision decision=Decision::no_task;
    Task task;
    bool needs_conversion=false;
    Disposition disposition=Disposition::none;
};
class Owner {
    struct Suppression {Key key;Reason reason;std::uint64_t fact;};
    std::vector<Suppression> suppressed;
    Task current;
    Resources previous;
    bool observed=false,recovering=false;
    std::uint64_t last_execution=0;
    bool suppress(Key,Reason,std::uint64_t);
    bool excluded(const Candidate&)const;
    const GroupObservation* group(const Observation&)const;
    bool reconcile_task(const Observation&);
public:
    static constexpr unsigned capacity=512;
    std::uint64_t held_bag=0;
    float confirmed_damage=0;
    unsigned observed_gold_receipts=0,observed_gem_receipts=0;
    bool capacity_failed=false;
    const Task& task()const{return current;}
    bool health_recovery()const{return recovering;}
    void apply(const Execution&);
    bool reopen(const Change&);
    // A new finite route/contact witness for the SAME committed semantic role.
    // This does not rerank utility, clear exclusions or recreate the owner.
    bool refresh_contact(const Candidate&);
    // Candidate preparation/route work may be deliberately deferred. False
    // complete_options retains the task; it never means no eligible objective.
    Directive update(const Observation&,const std::vector<Candidate>&,
                     bool complete_options=true);
};
}
