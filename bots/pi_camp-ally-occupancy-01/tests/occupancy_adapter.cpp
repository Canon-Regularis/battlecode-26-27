// Line protocol adapter: one process is one champion. No SDK or geometry model.
#include "ally_occupancy.h"
#include <iostream>
#include <map>
#include <string>
using namespace lp::occupancy;
int main(){
    Cache cache;Attempt last;int round=0;unsigned revision=0;std::string command;
    while(std::cin>>command){
        if(command=="roster") {int own,n;std::cin>>own>>n;std::vector<int> ids(n);for(auto& i:ids)std::cin>>i;cache.configure(ids,own);}
        else if(command=="key") {Key k;std::cin>>k.life>>k.task>>k.started;cache.reset(k);}
        else if(command=="batch") {
            Batch b;int normal,np,nv,na;std::cin>>b.round>>b.revision>>b.complete>>b.width>>b.height>>normal>>np;
            b.positives.resize(np);for(auto& p:b.positives)std::cin>>p.identity>>p.position.x>>p.position.y;
            std::cin>>nv;b.visible.resize(nv);for(auto& p:b.visible)std::cin>>p.x>>p.y;
            std::cin>>na;std::map<int,int> alive;for(int i=0;i<na;++i){int id,value;std::cin>>id>>value;alive[id]=value;}
            round=b.round;revision=b.revision;int queries=0;
            last=cache.prepare(b,normal,[&]{return round==b.round&&revision==b.revision;},[&](int id)->std::optional<bool>{++queries;auto i=alive.find(id);if(i==alive.end()||i->second<0)return {};return i->second!=0;});
            std::cout<<"mask "<<last.current<<' '<<queries<<' '<<last.uncertain.size();
            for(auto& t:last.uncertain)std::cout<<' '<<t.identity<<' '<<t.position.x<<' '<<t.position.y<<' '<<t.round<<' '<<t.observation<<' '<<t.version;
            std::cout<<std::endl;
        } else if(command=="feedback") {int outcome,complete;std::cin>>outcome>>round>>revision>>complete;cache.feedback(last,static_cast<Outcome>(outcome),round,revision,complete);}
        else return 2;
    }
}
