#include "service_work.h"
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
using namespace lp::economic::work;
void require(bool b){if(!b)throw std::runtime_error("checked arithmetic/probe contract");}
void print(const Wide& v){for(auto limb:v.limbs)std::cout<<' '<<limb;}
float read_atom(bool& known) {
    std::string raw;require(bool(std::cin>>raw));
    if(raw=="unknown"){known=false;return 0;}
    return std::bit_cast<float>(std::uint32_t(std::stoul(raw,nullptr,16)));
}
template<class T> Wide canonical(const Domain& d,T value) {
    if constexpr(std::is_same_v<T,Wide>)return value;
    else {Wide out;require(d.canonical(value,out));return out;}
}
struct Row {float hp,first,second;bool a,b;};
template<class T> void victims(const Domain& domain,const std::vector<Row>& rows) {
    T total{};unsigned removals=0;std::vector<Wide> details;
    for(auto row:rows) {
        T hp,a,b;require(domain.encode(row.hp,hp)&&domain.encode(row.first,a)&&domain.encode(row.second,b));
        if(!row.a)a={};
        if(!row.b)b={};
        const auto initial=hp.compare(a)<0?hp:a;
        T remaining;require(hp.subtract(initial,remaining));
        const auto marginal=b.compare(remaining)<0?b:remaining;
        T work;require(initial.add(marginal,work));require(total.add(work,total));
        removals+=unsigned(hp.compare(T{})>0&&work==hp);
        for(auto value:{initial,remaining,marginal,work})details.push_back(canonical(domain,value));
    }
    std::cout<<"S "<<domain.fast<<' '<<domain.q<<' '<<domain.high<<' '<<removals;
    print(canonical(domain,total));for(auto v:details)print(v);std::cout<<'\n';
}
int main(int argc,char**){try {
    if(argc==1) {
        Domain d;d.observe(1);d.observe(2);require(d.fast&&d.q==0);
        Small x,y;require(d.encode(1,x)&&d.encode(2,y)&&x.add(y,x)&&x.value==3);
        require(x.subtract(y,x)&&x.value==1&&!y.subtract(Small{3},x)&&x.value==1);
        Wide w;require(d.canonical(x,w));Wide one;require(d.encode(1,one)&&w==one);
        std::cout<<"PASS: exact service-work alias/checked-operation controls\n";return 0;
    }
    std::string command;
    while(std::cin>>command) {
        if(command=="A") {
            unsigned n;std::cin>>n;require(n<=2048);std::vector<float> values;bool known=true;Domain d;
            for(unsigned i=0;i<n;++i){auto f=read_atom(known);d.observe(f);values.push_back(f);}
            if(!known||!d.valid){std::cout<<"U\n";continue;}
            std::cout<<"S "<<d.fast<<' '<<d.q<<' '<<d.high;
            for(auto f:values) {
                Wide w;require(d.encode(f,w));
                if(d.fast){Small small;Wide back;require(d.encode(f,small)&&d.canonical(small,back)&&back==w);}
                print(w);
            }
            std::cout<<'\n';
        } else if(command=="F") {
            unsigned n;std::cin>>n;require(n&&n<=256);std::vector<Row> rows;bool known=true;Domain d;
            for(unsigned i=0;i<n;++i) {
                Row row;row.hp=read_atom(known);row.first=read_atom(known);row.second=read_atom(known);
                std::cin>>row.a>>row.b;d.observe(row.hp);d.observe(row.first);d.observe(row.second);rows.push_back(row);
            }
            if(!known||!d.valid){std::cout<<"U\n";continue;}
            if(d.fast)victims<Small>(d,rows);else victims<Wide>(d,rows);
        } else if(command=="L") {
            Wide a,b,sum,difference;for(auto& x:a.limbs)std::cin>>x;for(auto& x:b.limbs)std::cin>>x;
            const bool added=a.add(b,sum),subtracted=a.subtract(b,difference);
            std::cout<<"L "<<added;print(sum);std::cout<<' '<<subtracted;print(difference);std::cout<<'\n';
        } else throw std::runtime_error("unknown probe command");
    }
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
