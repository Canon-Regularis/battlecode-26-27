#include "service_work.h"
namespace lp::economic::work {
namespace {
bool atom(float f,std::uint32_t& m,int& exponent) {
    const auto bits=std::bit_cast<std::uint32_t>(f),fraction=bits&0x7fffffu,e=(bits>>23)&255u;
    if(e==255u||((bits>>31)&&(e||fraction)))return false;
    m=e?fraction|0x800000u:fraction;exponent=e?int(e)-150:-149;return true;
}
bool shifted(std::uint64_t value,unsigned shift,Wide& result) {
    Wide out;const unsigned word=shift/64,bit=shift%64;
    if(!value){result=out;return true;}
    if(word>=5)return false;
    out.limbs[word]=value<<bit;
    if(bit) {
        const auto upper=value>>(64-bit);
        if(word==4&&upper)return false;
        if(word<4)out.limbs[word+1]=upper;
    }
    result=out;return true;
}
}
int Wide::compare(const Wide& b)const {
    for(int i=4;i>=0;--i)if(limbs[i]!=b.limbs[i])return limbs[i]<b.limbs[i]?-1:1;
    return 0;
}
bool Wide::add(const Wide& b,Wide& result)const {
    Wide out;bool carry=false;
    for(unsigned i=0;i<5;++i) {
        const auto first=limbs[i]+b.limbs[i];const bool c1=first<limbs[i];
        out.limbs[i]=first+unsigned(carry);carry=c1||out.limbs[i]<first;
    }
    if(carry)return false;
    result=out;return true;
}
bool Wide::subtract(const Wide& b,Wide& result)const {
    if(compare(b)<0)return false;
    Wide out;bool borrow=false;
    for(unsigned i=0;i<5;++i) {
        const auto first=limbs[i]-b.limbs[i];const bool b1=limbs[i]<b.limbs[i];
        out.limbs[i]=first-unsigned(borrow);borrow=b1||first<unsigned(borrow);
    }
    if(borrow)return false;
    result=out;return true;
}
void Domain::observe(float f) {
    std::uint32_t m;int exponent;
    if(!atom(f,m,exponent)){valid=false;return;}
    if(!m)return;
    const int low=exponent+std::countr_zero(m),hi=exponent+31-std::countl_zero(m);
    if(!nonzero){q=low;high=hi;nonzero=true;}
    else {if(low<q)q=low;if(hi>high)high=hi;}
    fast=high-q+1+8<=64;
}
bool Domain::encode(float f,Wide& out)const {
    std::uint32_t m;int exponent;
    return valid&&atom(f,m,exponent)&&shifted(m,unsigned(exponent+149),out);
}
bool Domain::encode(float f,Small& out)const {
    std::uint32_t m;int exponent;
    if(!valid||!fast||!atom(f,m,exponent))return false;
    if(!m){out={};return true;}
    const int trailing=std::countr_zero(m),shift=exponent+trailing-q;
    m>>=trailing;
    if(shift<0||shift>=64||std::uint64_t(m)>(UINT64_MAX>>shift))return false;
    out.value=std::uint64_t(m)<<shift;return true;
}
bool Domain::canonical(Small value,Wide& out)const {
    return valid&&fast&&q>=-149&&shifted(value.value,unsigned(q+149),out);
}
}
