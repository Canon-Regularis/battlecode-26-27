#pragma once
#include "model.h"
#include <iostream>
namespace lp {
struct Telemetry {
    std::array<unsigned,13> dwell{};
    unsigned errors=0,moves=0,captures=0,banks=0,defers=0,resumes=0,stale=0;
    void error(const char* what) {++errors;if(errors<=8||errors%100==0)std::cout<<"LP_ERROR count="<<errors<<" "<<what<<'\n';}
    void report(int r,int slot,int bag,int task) const {
        std::cout<<"LP round="<<r<<" slot="<<slot<<" bag="<<bag<<" task="<<task<<" banks="<<banks<<" captures="<<captures<<" moves="<<moves<<" deferred="<<defers<<" resumes="<<resumes<<" stale="<<stale<<" errors="<<errors<<" dwell=";
        for(auto n:dwell)std::cout<<n<<',';std::cout<<'\n';
    }
};
}
