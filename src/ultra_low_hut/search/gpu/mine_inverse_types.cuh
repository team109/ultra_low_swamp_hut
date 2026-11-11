#pragma once
#include "mine_layout26.h"
#include <cuda_runtime.h>
#include <vector>
using namespace mine26;
struct MineTemplate {
  uint64_t original, target;
  int relx, relz, width, g53, g54, covered, pieces;
};
struct MappedMine {
  uint64_t seed;
  int cx, cz, x, z, width, g53, g54, covered, pieces, index;
};
