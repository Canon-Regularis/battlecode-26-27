#pragma once
#include <functional>
#include <vector>

// C++ translation of SubhanAfz's SDK-independent LoopPlanner, commit 97f761f.
// Distances are supplied by CAMBC native BFS; this is strategic route search.
namespace subhan {
struct Camp {int gems=0,gold=0,service=0,respawn=0;};
struct Inputs {
    std::vector<Camp> camps;
    std::vector<std::vector<int>> distances,altar_distances;
    std::vector<int> spawn_distances;
    std::vector<double> camp_risk,altar_risk;
};
struct Config {
    int beam_width=8,max_camps=10,max_expansions=20000,report_limit=5;
    double gold_weight=.02,opening_weight=.15,risk_tolerance=.2;
};
struct Evaluation {
    int gems=0,gold=0,active=0,period=0,first_deposit=0,travel=0,service=0,tribute=0;
    double score=0,risk=0,multiplier=1,base_score=0;
    bool valid=false;
};
struct Loop {int altar=0;std::vector<int> route;Evaluation evaluation;};
Evaluation evaluate(const Inputs&,const Config&,const std::vector<int>& route,int altar);
std::vector<Loop> find_loops(const Inputs&,const Config&,const std::function<bool()>& stop=[] {return false;});
}
