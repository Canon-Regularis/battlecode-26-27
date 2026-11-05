#pragma once
#include "model.h"
namespace lp {
inline bool channel_start_allowed(bool alive,bool stunned,bool active,bool completed,bool started) {
    return alive&&!stunned&&!active&&!completed&&!started;
}
inline void apply_feature_commitments(Facts& f,bool camp,bool bank,bool attack) {
    if(camp||bank){f.danger=false;f.recovery=false;f.bank_needed=false;}
    if(attack){f.danger=false;f.recovery=false;}
}
}
