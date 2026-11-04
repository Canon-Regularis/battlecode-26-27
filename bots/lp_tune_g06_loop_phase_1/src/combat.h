#pragma once
#include "objectives.h"
namespace lp {
bool fight(World&,int task,bool travel=false);
bool defend_cast(const Snapshot&);
void optional_ward(const World&,int task);
}
