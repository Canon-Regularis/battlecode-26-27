// Pure contracts: use the real protocol/state code and extracted geometry bodies.
// This deliberately does not simulate engine vision, movement or shared-memory timing.
#include "model.h"
#include "protocol.h"
#include "geometry-under-test.h"
#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <vector>

using namespace lp;
static std::uint64_t checks=0;
static void require(bool condition,const char* property) {
    ++checks;
    if(!condition){std::cerr<<"FAIL: "<<property<<'\n';std::exit(1);}
}

int main() {
    std::uint64_t tiles=0,centers=0,packets=0;
    unsigned dimensions=0;
    for(int width=30;width<=100;++width)for(int height=30;height<=100;++height) {
        World world{width,height,(width+14)/15,(height+14)/15};
        ++dimensions;
        int count=world.columns*world.rows;
        require(count<=49&&count<63,"chunk addresses fit the six-bit field and exclude sentinel");
        struct Bounds {int x0=1000,y0=1000,x1=-1,y1=-1,area=0;};
        std::vector<Bounds> bounds(count);
        for(int y=0;y<height;++y)for(int x=0;x<width;++x) {
            ++tiles;
            int chunk=world.chunk({x,y});
            require(chunk>=0&&chunk<count,"every legal tile has a legal chunk");
            auto center=world.center(chunk);
            require(std::max(std::abs(center.x-x),std::abs(center.y-y))<=7,
                "nominal center is within seven Chebyshev tiles, before occlusion");
            auto& b=bounds[chunk];++b.area;
            b.x0=std::min(b.x0,x);b.x1=std::max(b.x1,x);
            b.y0=std::min(b.y0,y);b.y1=std::max(b.y1,y);
        }
        int min_width=1000,max_width=0,min_height=1000,max_height=0;
        for(int chunk=0;chunk<count;++chunk) {
            ++centers;
            auto center=world.center(chunk);auto b=bounds[chunk];
            require(b.area>0,"no empty chunk");
            require(center.x>=0&&center.x<width&&center.y>=0&&center.y<height,
                "centers stay inside the map");
            require(world.chunk(center)==chunk,"center round trip preserves the chunk");
            require(center.x==(b.x0+b.x1)/2&&center.y==(b.y0+b.y1)/2,
                "center agrees with independently enumerated membership bounds");
            int w=b.x1-b.x0+1,h=b.y1-b.y0+1;
            require(w<=15&&h<=15&&b.area==w*h,"each chunk is a full rectangle at most 15 by 15");
            min_width=std::min(min_width,w);max_width=std::max(max_width,w);
            min_height=std::min(min_height,h);max_height=std::max(max_height,h);
        }
        require(max_width-min_width<=1&&max_height-min_height<=1,"partitions are balanced");
    }

    const auto empty=wire::empty();
    require(wire::valid(empty,0),"empty word initializes the protocol");
    require(!wire::live(empty,0,6,49)&&!wire::leader_live(empty,0,6),"initialization creates no intent or leader");
    require(wire::get(empty,61,3)==0,"writer leaves reserved bits zero");
    for(unsigned bits=1;bits<=12;++bits)for(unsigned offset=0;offset+bits<=64;++offset) {
        for(auto base:{std::uint64_t{0},~std::uint64_t{0},std::uint64_t{0xaaaaaaaaaaaaaaaa}}) {
            for(unsigned value=0;value<=wire::mask(bits);++value) {
                auto word=wire::put(base,offset,bits,value);
                require(wire::get(word,offset,bits)==value,"field round trip");
                require((word&~(wire::mask(bits)<<offset))==(base&~(wire::mask(bits)<<offset)),
                    "field updates preserve every unrelated bit");
            }
        }
    }
    for(int round=0;round<=2000;++round)for(int slot=0;slot<6;++slot)
        for(int chunk=0;chunk<49;++chunk)for(int kind=1;kind<=2;++kind) {
            ++packets;
            auto packet=wire::create(empty,slot,round,kind,chunk);
            require(wire::get(packet,wire::owner,3)==unsigned(slot)&&
                wire::get(packet,wire::created,11)==unsigned(round)&&
                wire::get(packet,wire::chunk,6)==unsigned(chunk)&&
                wire::get(packet,wire::type,2)==unsigned(kind),"request fields round trip without timestamp wrapping");
            require(wire::live(packet,round,6,49)==(Config::rally_life>0),"request admission at creation");
            require(!wire::live(packet,round-1,6,49),"future request is not live");
            require(!wire::live(packet,round+Config::rally_life,6,49),"absolute request expiry");
            require(!wire::same(packet,wire::create(empty,(slot+1)%6,round,kind,chunk)),"different creators have different identities");
            if(round<2000)require(!wire::same(packet,wire::create(empty,slot,round+1,kind,chunk)),
                "same owner and target next round is a different attempt");
            auto cleared=wire::clear(packet);
            require(!wire::live(cleared,round,6,49)&&!wire::same(packet,cleared),"cleared request cannot remain live or owned");
            require(wire::get(cleared,wire::safety,12)==wire::get(empty,wire::safety,12),"rally cancellation preserves safety data");
        }
    auto packet=wire::create(empty,0,100,1,0);
    require(!wire::live(wire::put(packet,wire::owner,3,6),100,6,49),"out-of-roster owner rejected");
    require(!wire::live(wire::put(packet,wire::chunk,6,63),100,6,49),"absent chunk cannot become a destination");
    require(!wire::live(wire::put(packet,wire::type,2,3),100,6,49),"reserved request kind rejected");
    for(unsigned version=0;version<8;++version)if(version!=1)
        require(!wire::live(wire::put(packet,wire::version,3,version),100,6,49),"unknown versions disable requests");
    for(int slot=0;slot<6;++slot)for(int round=0;round<=2000;++round) {
        auto leader=wire::put(wire::put(empty,wire::leader,3,slot),wire::heartbeat,11,round);
        require(wire::leader_live(leader,round,6),"new leader heartbeat is live");
        require(!wire::leader_live(leader,round-1,6),"future leader heartbeat rejected");
        require(!wire::leader_live(leader,round+Config::lease+1,6),"leadership lease expires");
    }

    // Vary lower-priority objectives while asserting safety/scoring precedence.
    for(unsigned flags=0;flags<256;++flags) {
        Facts f;Memory m;
        f.bank_needed=flags&1;f.bank_protect=flags&2;f.camp_valid=flags&4;
        f.reward=flags&8;f.occupied=flags&16;f.leader=flags&32;f.rally=flags&64;
        if(flags&128)m.guidance_seen=100;
        f.alive=false;require(decide(f,m)==State::dead,"death beats every objective");
        f.alive=true;f.tribute=true;f.danger=true;
        require(decide(f,m)==State::bank,"existing tribute channel survives discretionary danger handling");
        f.tribute=false;f.teleport=true;
        require(decide(f,m)==State::bank,"existing teleport channel survives discretionary danger handling");
        f.teleport=false;require(decide(f,m)==State::escape,"danger beats banking, camps, protection and rally");
        f.danger=false;f.bank_needed=true;
        require(decide(f,m)==State::prepare_bank,"bank intent beats all lower objectives");
    }
    Facts free;Memory memory;
    require(decide(free,memory)==State::explore,"no shared leader is needed for autonomous exploration");
    free.rally=true;
    require(decide(free,memory)==State::rally,"pure selector accepts a synthetic rally fact, not proof the caller creates it");
    free.bank_protect=true;
    require(decide(free,memory)==State::protect,"visible carrier protection precedes a synthetic rally");
    require(bank_due(Config::bank_bag,-1,0,0)&&!bank_due(Config::bank_bag-1,-1,0,0),"configured banking threshold");
    require(bank_due(1,0,Config::bag_age,0)&&!bank_due(1,0,Config::bag_age-1,0),"configured bag-age deadline");
    require(bank_due(1,-1,0,999),"winning bag banks before normal threshold");
    require(task_expired(Config::task_limit,0,Config::task_limit-1),"task absolute age is bounded despite progress");
    require(task_expired(Config::stall,0,0),"task stalls expire independently of absolute lifetime");
    std::cout<<"{\"status\":\"pass\",\"checks\":"<<checks<<",\"map_dimensions\":"<<dimensions
        <<",\"tiles\":"<<tiles<<",\"centers\":"<<centers<<",\"requests\":"<<packets<<"}\n";
}
