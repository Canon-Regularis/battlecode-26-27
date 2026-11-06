#pragma once
#include <array>
#include <bit>
#include <cstdint>
#include <limits>
#include <span>
namespace lp::economic::work {
static_assert(sizeof(float)==4 && std::numeric_limits<float>::is_iec559 &&
    std::numeric_limits<float>::radix==2 && std::numeric_limits<float>::digits==24 &&
    std::numeric_limits<float>::max_exponent==128 && std::numeric_limits<float>::min_exponent==-125);
// Canonical nonnegative binary32 dyadics, in units of 2^-149. Arithmetic is
// checked even outside the service fold's <=256 capped-victim bound.
struct Wide {
    std::array<std::uint64_t,5> limbs{};
    int compare(const Wide&)const;
    bool add(const Wide&,Wide&)const;
    bool subtract(const Wide&,Wide&)const;
    friend bool operator==(const Wide&,const Wide&)=default;
};
struct Small {
    std::uint64_t value=0;
    int compare(Small b)const{return value<b.value?-1:value>b.value?1:0;}
    bool add(Small b,Small& out)const {
        if(b.value>UINT64_MAX-value)return false;
        out.value=value+b.value;return true;
    }
    bool subtract(Small b,Small& out)const {
        if(value<b.value)return false;
        out.value=value-b.value;return true;
    }
    friend bool operator==(Small,Small)=default;
};
struct Domain {
    bool valid=true,fast=true,nonzero=false;
    int q=0,high=0;
    // Observe every raw atom used in a scene BEFORE selecting its fold mode.
    // Dirty scenes must rebuild the domain and re-encode all carried atoms.
    void observe(float);
    bool encode(float,Wide&)const;
    bool encode(float,Small&)const;
    bool canonical(Small,Wide&)const;
};
}
