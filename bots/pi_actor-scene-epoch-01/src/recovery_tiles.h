#pragma once
#include "recovery.h"
namespace lp::recovery {
// Public coordinate export -> owned controller bytes. No engine layout assumptions.
inline int scalar_cells(int width,int height) {
    if(width<=0||height<=0||width>Limits::cells/height)throw Halt{Status::incomplete};
    return width*height;
}
template<class Coordinates>
std::vector<unsigned char> scalar_tiles(int width,int height,const Coordinates& coordinates) {
    const int cells=scalar_cells(width,height);
    if(coordinates.size()>std::size_t(cells))throw Halt{Status::incomplete};
    std::vector<unsigned char> bytes(cells,0);
    for(auto p:coordinates) {
        if(p.x<0||p.y<0||p.x>=width||p.y>=height)throw Halt{Status::incomplete};
        bytes[p.y*width+p.x]=1;
    }
    return bytes;
}
}
