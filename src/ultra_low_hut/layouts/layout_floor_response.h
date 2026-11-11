#pragma once
#include "mine_layout26.h"
#include <stdint.h>

#ifdef __CUDACC__
#define ORDERED_FLOOR_HD __host__ __device__
#else
#define ORDERED_FLOOR_HD
#endif

namespace ordered_floor {

// Flat H=-54, Y=-64..-53 occupancy. Roofs are all allowed, fluids and
// non-floor supports are omitted. This is a ranking approximation, not a
// vanilla-equivalent result or a necessary bound under randomized roof
// branches.
struct Score {
  int idealAllAirGain;
  int orderedFloorGain;
  int bridgeColumns;
  int protectedFloorColumns;
  int floorPlankWrites;
};

ORDERED_FLOOR_HD inline int columnHeight(uint32_t solid) {
  if (!solid)
    return -64;
#ifdef __CUDA_ARCH__
  return 31 - __clz(solid) - 63;
#else
  return 31 - __builtin_clz(solid) - 63;
#endif
}

ORDERED_FLOOR_HD inline Score scoreFlat54(const mine26::Layout &layout,
                                          int originX, int originZ,
                                          int width = 7,
                                          int *idealHeights = nullptr,
                                          int *orderedHeights = nullptr,
                                          uint32_t *protectedFloors = nullptr) {
  Score score{0, 0, 0, 0, 0};
  for (int column = 0; column < 63; ++column) {
    const int x = column % width, z = column / width;
    uint32_t ideal = 0x3ffu, solid = ideal, wood = 0;
    for (int index = 0; index < layout.n; ++index) {
      const auto &piece = layout.p[index];
      uint32_t clearing = 0;
      for (int y = -64; y <= -53; ++y) {
        if (mine26::canClearAt(layout, index, x, y, z, originX, originZ))
          clearing |= uint32_t(1) << (y + 64);
      }
      ideal &= ~clearing;
      solid &= ~(clearing & ~wood);
      if (piece.type != 1)
        continue;
      const auto &box = piece.b;
      const int floorY = box.y0 - 1;
      if (x < box.x0 || x > box.x1 || z < box.z0 || z > box.z1 ||
          floorY < -64 || floorY > -53)
        continue;
      const uint32_t floorBit = uint32_t(1) << (floorY + 64);
      // StructurePiece.isInterior queries Y+1 against OCEAN_FLOOR_WG.
      if (!(solid & floorBit) && floorY + 1 < columnHeight(solid)) {
        solid |= floorBit;
        wood |= floorBit;
        ++score.floorPlankWrites;
      }
    }
    const int idealHeight = columnHeight(ideal);
    const int orderedHeight = columnHeight(solid);
    score.idealAllAirGain += -54 - idealHeight;
    score.orderedFloorGain += -54 - orderedHeight;
    score.protectedFloorColumns += wood != 0;
    if (solid && (wood & (uint32_t(1) << (orderedHeight + 63))))
      ++score.bridgeColumns;
    if (idealHeights)
      idealHeights[column] = idealHeight;
    if (orderedHeights)
      orderedHeights[column] = orderedHeight;
    if (protectedFloors)
      protectedFloors[column] = wood;
  }
  return score;
}

} // namespace ordered_floor
#undef ORDERED_FLOOR_HD
