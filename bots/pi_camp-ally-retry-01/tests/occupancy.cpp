#include "ally_occupancy.h"
#include <cassert>
#include <iostream>
using namespace lp::occupancy;
int main() {
    Cache c;c.configure({1,2,3},1);c.reset({1,4,10});
    int round=10;unsigned revision=1;int calls=0;bool live=true,current=true;
    auto run=[&](Batch b,bool normal=true){return c.prepare(b,normal,[&]{return current&&b.round==round&&b.revision==revision;},[&](int identity)->std::optional<bool>{assert(identity==2||identity==3);++calls;return live;});};
    Batch b;b.round=10;b.revision=1;b.complete=true;b.positives={{1,{1,1}},{2,{2,2}},{99,{3,3}},{3,{-1,0}}};
    assert(run(b).uncertain.empty()&&calls==0);
    b.positives.clear();++round;b.round=round;
    auto a=run(b);assert(a.current&&a.uncertain.size()==1&&calls==1);
    auto t=a.uncertain[0];assert(t.round==10&&t.observation==1);
    assert(run(b).uncertain[0]==t&&calls==1); // reuse is not a positive observation
    c.feedback(a,Outcome::no_route,round,revision,true);
    assert(run(b).uncertain.size()==1&&calls==1); // same round never relaxes
    ++round;b.round=round;assert(run(b).uncertain.empty()&&calls==2);
    assert(run(b).uncertain.empty()); // old hidden snapshot cannot reconstruct deleted record
    b.positives={{2,{2,2}}};++revision;b.revision=revision;run(b);
    b.positives.clear();++round;b.round=round;a=run(b);
    c.feedback(a,Outcome::no_route,round,revision,true);
    b.positives={{2,{2,2}}};++revision;b.revision=revision;run(b,false); // fresher same-round positive wins
    b.positives.clear();++round;b.round=round;assert(run(b).uncertain.size()==1);
    // Moved and clear evidence affects precisely one identity.
    b.positives={{2,{4,4}},{3,{2,2}}};++revision;b.revision=revision;run(b);
    b.positives={{3,{2,2}}};b.visible={{4,4}};++round;b.round=round;assert(run(b).uncertain.empty());
    b.positives.clear();b.visible.clear();++round;b.round=round;a=run(b);assert(a.uncertain.size()==1&&a.uncertain[0].identity==3);
    live=false;++round;b.round=round;assert(run(b).uncertain.empty());live=true;
    for(Key key: {Key{2,4,10},Key{2,5,10},Key{2,5,11},Key{2,-1,11}}) {
        c.reset({1,4,10});b.positives={{2,{2,2}}};run(b);c.reset(key);b.positives.clear();assert(run(b).uncertain.empty());
    }
    c.reset({3,4,10});b.positives={{2,{2,2}}};b.complete=false;run(b);b.complete=true;b.positives.clear();assert(run(b).uncertain.empty());
    b.positives={{2,{100,0}},{3,{0,100}}};run(b);b.positives.clear();assert(run(b).uncertain.empty());
    // Before and after guard failure publish no partial update, including death.
    b.positives={{2,{2,2}}};current=false;run(b);current=true;b.positives.clear();assert(run(b).uncertain.empty());
    b.positives={{2,{2,2}}};int guards=0;
    c.prepare(b,true,[&]{return ++guards==1;},[](int)->std::optional<bool>{return true;});
    b.positives.clear();assert(run(b).uncertain.empty());
    // Future and stale batches cannot add positions through the same current predicate.
    b.positives={{2,{2,2}}};++b.round;run(b);b.round=round;b.revision=revision+1;run(b);b.revision=revision;b.positives.clear();assert(run(b).uncertain.empty());
    // Only complete exact attempts can schedule deletion.
    for(auto outcome:{Outcome::other,Outcome::no_route,Outcome::overlay_empty}) {
        b.positives={{2,{2,2}}};run(b);b.positives.clear();++round;b.round=round;a=run(b);
        c.feedback(a,outcome,round,revision,false);c.feedback(a,outcome,round,revision+1,true);
        ++round;b.round=round;assert(run(b).uncertain.size()==1);
        c.feedback(run(b),outcome,round,revision,true);++round;b.round=round;
        assert(run(b).uncertain.empty()==(outcome!=Outcome::other));
        c.reset({++round,4,10});b.round=round;
    }
    // Failed hidden alive query is unknown and counted once, even across revisions.
    b.positives={{2,{2,2}}};run(b);b.positives.clear();++round;b.round=round;calls=0;
    auto unknown=[&](int)->std::optional<bool>{++calls;return {};};
    auto guard=[&]{return true;};
    assert(c.prepare(b,true,guard,unknown).uncertain.size()==1);
    ++b.revision;assert(c.prepare(b,true,guard,unknown).uncertain.size()==1&&calls==1);
    // Stale post-probe cannot fabricate death, or repeat the probe in this round.
    b.revision=revision;b.positives={{2,{2,2}}};run(b);b.positives.clear();++round;b.round=round;calls=guards=0;
    c.prepare(b,true,[&]{return ++guards==1;},[&](int)->std::optional<bool>{++calls;return false;});
    assert(run(b).uncertain.size()==1&&calls==1); // failed guard discarded death, call accounting survived
    std::cout<<"PASS occupancy module: identity/version/reset/deferred deletion and alive query bounds\n";
}
