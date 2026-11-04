#include "loop_planner.h"
#include <iomanip>
#include <iostream>
int main() {
    int cases;std::cin>>cases;
    while(cases--) {
        int n,a;subhan::Config c;std::cin>>n>>a>>c.beam_width>>c.max_camps>>c.max_expansions>>c.report_limit>>c.gold_weight>>c.opening_weight>>c.risk_tolerance;
        subhan::Inputs d;d.camps.resize(n);d.spawn_distances.resize(n);d.camp_risk.resize(n);d.altar_risk.resize(a);
        for(int i=0;i<n;++i){auto& g=d.camps[i];std::cin>>g.gems>>g.gold>>g.service>>g.respawn>>d.spawn_distances[i]>>d.camp_risk[i];}
        d.distances.assign(n,std::vector<int>(n));d.altar_distances.assign(a,std::vector<int>(n));
        for(auto& row:d.distances)for(int& v:row)std::cin>>v;
        for(auto& row:d.altar_distances)for(int& v:row)std::cin>>v;
        for(double& v:d.altar_risk)std::cin>>v;
        auto loops=subhan::find_loops(d,c);std::cout<<loops.size();
        for(const auto& l:loops){std::cout<<' '<<l.altar<<' '<<l.route.size();for(int i:l.route)std::cout<<' '<<i;std::cout<<' '<<std::setprecision(17)<<l.evaluation.score<<' '<<l.evaluation.period<<' '<<l.evaluation.first_deposit;}
        std::cout<<'\n';
    }
}
