#pragma once
#include <algorithm>
namespace lp {
struct ChunkBounds {int x0=0,y0=0,x1=-1,y1=-1;bool valid() const{return x0<=x1&&y0<=y1;}};
inline int chunk_count(int width,int height){
    return width>=1&&width<=100&&height>=1&&height<=100?((width+14)/15)*((height+14)/15):0;
}
inline int chunk_of(int width,int height,int x,int y){
    if(!chunk_count(width,height)||x<0||y<0||x>=width||y>=height)return 63;
    int columns=(width+14)/15,rows=(height+14)/15;
    return (y*rows/height)*columns+x*columns/width;
}
inline ChunkBounds chunk_bounds(int width,int height,int id){
    int count=chunk_count(width,height);if(id<0||id>=count)return {};
    int columns=(width+14)/15,rows=(height+14)/15,x=id%columns,y=id/columns;
    return {(x*width+columns-1)/columns,(y*height+rows-1)/rows,
        ((x+1)*width+columns-1)/columns-1,((y+1)*height+rows-1)/rows-1};
}
enum class InspectionResult {found,contact,moving,defer,expired,replaced,ambiguous,no_match_now,no_viewpoint,blocked,exhausted};
struct InspectionBudget {
    int started=-1,steps=0,views=0,stalled=0;
    bool exhausted(int round,int turns,int max_steps,int max_views) const{
        return started>=0&&(round-started>=turns||steps>=max_steps||views>=max_views);
    }
};
struct ScanPoint {int x=-1,y=-1,phase=3;};
inline ScanPoint next_inspection_candidate(ChunkBounds b,int width,int height,int& phase,int& cursor){
    while(phase<3){
        int x0=phase<2?b.x0:std::max(0,b.x0-8),x1=phase<2?b.x1:std::min(width-1,b.x1+8);
        int y0=phase<2?b.y0:std::max(0,b.y0-8),y1=phase<2?b.y1:std::min(height-1,b.y1+8);
        int span=x1-x0+1,total=span*(y1-y0+1);
        if(cursor>=total){cursor=0;++phase;continue;}
        int index=cursor++;return {x0+index%span,y0+index/span,phase};
    }
    return {};
}
}
