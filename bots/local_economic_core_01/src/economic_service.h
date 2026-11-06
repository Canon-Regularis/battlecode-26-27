#pragma once
#include "economic_scene.h"
#include "service_work.h"
namespace lp::economic {
enum class ServiceStop { action, holding, allowance, cooldown, no_contact,
    unsafe, unknown_wake, unsupported, incomplete, capacity };
struct ServiceIntent {
    Key key;
    // Comparable retained next contact, not a Euclidean substitute for a route.
    Point contact;
    bool has_contact=false;
    bool recovering=false;
};
struct ServiceChoice {
    ServiceStop stop=ServiceStop::no_contact;
    action::Request request;
    work::Wide nominal_work;
    unsigned removals=0,contributions=0;
    bool fast_domain=false;
    bool enemy=false; // compatible stationary capture defense, never camp damage pricing
};
// Pure scalar fold. Returns ONE operation. Continuations are estimates used
// only for ranking; a fresh scene and fold are required after every attempt.
ServiceChoice select_service(const Scene&,ServiceIntent,const action::Ledger&);
}
