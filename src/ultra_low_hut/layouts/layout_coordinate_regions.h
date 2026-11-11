#pragma once
#include <stdint.h>

#ifdef __CUDACC__
#define LAYOUT_COORDINATE_HD __host__ __device__
#else
#define LAYOUT_COORDINATE_HD
#endif

namespace layout_coordinates {

// Room starts at the 16-aligned hut anchor + 2. World-border coordinates use
// three float precision regimes; exact negative boundaries belong to the
// smaller-magnitude regime because the room extends toward positive
// coordinates.
enum class CoordinatePrecision : uint8_t {
  SubBlock = 0,
  OneBlock = 1,
  TwoBlocks = 2,
};

constexpr int kPrecisionClassCount = 3;
constexpr int kCoordinateRegionCount = 9;

struct CoordinateRepresentative {
  int x;
  int z;
};

LAYOUT_COORDINATE_HD constexpr CoordinatePrecision
coordinatePrecision(int anchor) {
  const uint32_t magnitude =
      anchor < 0 ? uint32_t(-int64_t(anchor) - 1) : uint32_t(anchor);
  return magnitude < (uint32_t(1) << 23)   ? CoordinatePrecision::SubBlock
         : magnitude < (uint32_t(1) << 24) ? CoordinatePrecision::OneBlock
                                           : CoordinatePrecision::TwoBlocks;
}

LAYOUT_COORDINATE_HD constexpr int coordinateRegionIndex(int x, int z) {
  return kPrecisionClassCount * int(coordinatePrecision(x)) +
         int(coordinatePrecision(z));
}

LAYOUT_COORDINATE_HD constexpr int
representativeAxisCoordinate(CoordinatePrecision precision) {
  return precision == CoordinatePrecision::SubBlock   ? 0
         : precision == CoordinatePrecision::OneBlock ? 12582912
                                                      : 20000000;
}

LAYOUT_COORDINATE_HD constexpr CoordinateRepresentative
coordinateRepresentative(int region) {
  return {
      representativeAxisCoordinate(
          CoordinatePrecision(region / kPrecisionClassCount)),
      representativeAxisCoordinate(
          CoordinatePrecision(region % kPrecisionClassCount)),
  };
}

} // namespace layout_coordinates

#undef LAYOUT_COORDINATE_HD
