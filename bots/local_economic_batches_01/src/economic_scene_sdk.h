#pragma once
#include "economic_scene.h"
#include "live_turn.h"
#include "objectives.h"
namespace lp {
class EconomicCapture {
    struct Descriptor {
        camp handle;
        unsigned key;
        int group,range;
        economic::Point last;
        float prior_hp;
        bool passive;
    };
    struct Identity {unsigned key,index;};
    std::vector<Descriptor> descriptors;
    std::vector<Identity> identities;
    std::vector<economic::Life> lifecycle;
    std::vector<int> cycles;
    bool initialized=false;
    bool cached=false;
    economic::Scene previous;
    void prepare(World&,LiveTurn&);
public:
    // A complete immutable scene is published only after final epoch validation.
    // No private SDK record/import is read here. Dynamic rows hold scalar facts.
    economic::Scene capture(World&,LiveTurn&,int selected_group=-1);
};
}
