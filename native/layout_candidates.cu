#include <cuda_runtime.h>
#ifndef HUNT_ROOM_MAX_Y
#define HUNT_ROOM_MAX_Y -62
#endif
#define MINE26_PACKED_COLLISION
#undef HUNT_ROOM_MAX_Y
#define HUNT_ROOM_MAX_Y -58
#include "layout_coordinate_regions.h"
#include "layout_floor_response.h"
#include "mine_layout26.h"

__device__ unsigned long long TARGET_STATS[5];
__device__ unsigned OVERFLOW_COUNT;
__device__ uint64_t OVERFLOW_TARGETS[4096];
struct LayoutCandidate {
  uint64_t target;
  int g53, g54, far53, far54, covered, pieces, roomWidth, roomHeight, roomDepth,
      bottom;
  int originX, originZ, corridorGain, hutWidth, regionMask, orderedGain,
      bridgeColumns, deepCorridorGain;
};
static_assert(sizeof(LayoutCandidate) == 80, "Layout candidate ABI");
constexpr int REGION_COUNT = layout_coordinates::kCoordinateRegionCount;
// Same-chunk mineshaft placement constrains the first RNG double below 0.004,
// fixing the hut constructor's first nextInt(4) to NORTH (7x9).
struct RegionScore {
  int g53, g54, covered, ordered, bridges, withoutCorridor, withoutDeep;
};

__global__ void generateEligible(const uint64_t *targets, int n,
                                 mine26::Layout *scratch, int *eligible,
                                 int *eligibleCount, int *counts) {
  int i = blockIdx.x * blockDim.x + threadIdx.x;
  if (i >= n)
    return;
  auto &g = scratch[i];
  if (!g.generate(targets[i], 0, 0)) {
    if (!g.roomPruned) {
      atomicAdd(counts + 3, 1);
      unsigned slot = atomicAdd(&OVERFLOW_COUNT, 1u);
      if (slot < 4096)
        OVERFLOW_TARGETS[slot] = targets[i];
    }
    return;
  }
  int lowest = g.p[0].b.y0;
  for (int p = 1; p < g.n; p++)
    if (g.p[p].b.y0 < lowest)
      lowest = g.p[p].b.y0;
  int inside = -55 - g.p[0].b.y0, outside = -54 - lowest;
  if (inside < 0)
    inside = 0;
  if (outside < 0)
    outside = 0;
  if (35 * inside + 28 * outside < 315)
    return;
  atomicAdd(counts + 1, 1);
  bool rimCorridor = false;
  for (int p = 1; p < g.n && !rimCorridor; p++)
    if (g.p[p].type != 0) {
      auto box = g.p[p].b;
      if (box.y0 > -54 || box.y1 < -63)
        continue;
      bool west = box.x0 <= 1 && box.x1 >= 0 && box.z0 <= 8 && box.z1 >= 0;
      bool north = box.z0 <= 1 && box.z1 >= 0 && box.x0 <= 8 && box.x1 >= 0;
      rimCorridor = west || north;
    }
  if (rimCorridor)
    eligible[atomicAdd(eligibleCount, 1)] = i;
}

// All metrics share the same exact per-piece clearing masks. The ordered
// occupancy/floor update is the column body of ordered_floor::scoreFlat54.
__device__ RegionScore scoreColumn(const mine26::Layout &g, int column,
                                   int width, int ox, int oz) {
  const int x = column % width, z = column / width;
  uint32_t allClearing = 0, nonCorridorClearing = 0, withoutDeepClearing = 0;
  uint32_t solid = 0x3ffu, wood = 0;
  for (int p = 0; p < g.n; p++) {
    const auto &piece = g.p[p];
    uint32_t clearing = 0;
    for (int y = -64; y <= -53; y++)
      if (mine26::canClearAt(g, p, x, y, z, ox, oz))
        clearing |= uint32_t(1) << (y + 64);
    allClearing |= clearing;
    if (piece.type != 1)
      nonCorridorClearing |= clearing;
    if (!(piece.type == 1 && piece.b.y1 < -57))
      withoutDeepClearing |= clearing;
    solid &= ~(clearing & ~wood);
    if (piece.type != 1)
      continue;
    const auto &box = piece.b;
    const int floorY = box.y0 - 1;
    if (x < box.x0 || x > box.x1 || z < box.z0 || z > box.z1 || floorY < -64 ||
        floorY > -53)
      continue;
    const uint32_t floorBit = uint32_t(1) << (floorY + 64);
    if (!(solid & floorBit) &&
        floorY + 1 < ordered_floor::columnHeight(solid)) {
      solid |= floorBit;
      wood |= floorBit;
    }
  }
  int g53 = -53 - ordered_floor::columnHeight(0x7ffu & ~allClearing);
  int g54 = -54 - ordered_floor::columnHeight(0x3ffu & ~allClearing);
  int height = ordered_floor::columnHeight(solid);
  int bridge = solid && (wood & (uint32_t(1) << (height + 63)));
  return {g53,
          g54,
          int(g53 > 0 || g54 > 0),
          -54 - height,
          bridge,
          -54 - ordered_floor::columnHeight(0x3ffu & ~nonCorridorClearing),
          -54 - ordered_floor::columnHeight(0x3ffu & ~withoutDeepClearing)};
}

__global__ void scoreRegions(const mine26::Layout *scratch, const int *eligible,
                             RegionScore *scores) {
  const int item = blockIdx.x, regime = blockIdx.y;
  const int lane = threadIdx.x;
  __shared__ __align__(16) unsigned char layoutStorage[sizeof(mine26::Layout)];
  static_assert(sizeof(mine26::Layout) % sizeof(uint32_t) == 0,
                "Layout word copy");
  auto *words = reinterpret_cast<uint32_t *>(layoutStorage);
  const auto *source =
      reinterpret_cast<const uint32_t *>(scratch + eligible[item]);
  for (int j = lane; j < int(sizeof(mine26::Layout) / sizeof(uint32_t));
       j += 64)
    words[j] = source[j];
  __syncthreads();
  const auto &g = *reinterpret_cast<const mine26::Layout *>(layoutStorage);
  RegionScore score{};
  if (lane < 63) {
    auto origin = layout_coordinates::coordinateRepresentative(regime);
    score = scoreColumn(g, lane, 7, origin.x, origin.z);
  }
  __shared__ int reductions[7][64];
  reductions[0][lane] = score.g53;
  reductions[1][lane] = score.g54;
  reductions[2][lane] = score.covered;
  reductions[3][lane] = score.ordered;
  reductions[4][lane] = score.bridges;
  reductions[5][lane] = score.withoutCorridor;
  reductions[6][lane] = score.withoutDeep;
  __syncthreads();
  for (int stride = 32; stride; stride >>= 1) {
    if (lane < stride)
      for (int metric = 0; metric < 7; metric++)
        reductions[metric][lane] += reductions[metric][lane + stride];
    __syncthreads();
  }
  if (lane == 0)
    scores[item * REGION_COUNT + regime] = {
        reductions[0][0], reductions[1][0], reductions[2][0], reductions[3][0],
        reductions[4][0], reductions[5][0], reductions[6][0]};
}

__global__ void assembleCandidates(const uint64_t *targets,
                                   const mine26::Layout *scratch,
                                   const int *eligible, int eligibleCount,
                                   const RegionScore *scores, int minimum,
                                   int minimumOrdered, LayoutCandidate *out,
                                   int cap, int *counts) {
  const int item = blockIdx.x * blockDim.x + threadIdx.x;
  if (item >= eligibleCount)
    return;
  const int input = eligible[item];
  const auto &g = scratch[input];
  {
    int best = -1, bestOrdered = -1, bestGain = -1, regionMask = 0;
    const auto *regions = scores + item * REGION_COUNT;
    int overall = 0, overallRegion = 0;
    for (int regime = 0; regime < REGION_COUNT; regime++)
      if (regions[regime].g54 > overall) {
        overall = regions[regime].g54;
        overallRegion = regime;
      }
    atomicMax(counts, overall);
    const int thresholds[4] = {315, 330, 345, 360};
    for (int j = 0; j < 4; j++)
      if (overall >= thresholds[j])
        atomicAdd(TARGET_STATS + j, 1ULL);
    atomicMax(TARGET_STATS + 4, (uint64_t(overall) << 32) |
                                    (uint64_t(input) << 4) | overallRegion);
    for (int regime = 0; regime < REGION_COUNT; regime++) {
      const auto &s = regions[regime];
      if (s.g54 < minimum || s.ordered < minimumOrdered)
        continue;
      if (s.g54 > bestGain || (s.g54 == bestGain && s.ordered > bestOrdered)) {
        best = regime;
        bestOrdered = s.ordered;
        bestGain = s.g54;
      }
    }
    if (best < 0)
      return;
    for (int regime = 0; regime < REGION_COUNT; regime++) {
      const auto &s = regions[regime];
      if (s.g54 >= minimum)
        regionMask |= 1 << regime;
    }
    int slot = atomicAdd(counts + 2, 1);
    if (slot >= cap)
      return;
    const auto &chosen = regions[best];
    const auto &near = regions[0];
    auto origin = layout_coordinates::coordinateRepresentative(best);
    auto box = g.p[0].b;
    auto &r = out[slot];
    r.target = targets[input];
    r.g53 = near.g53;
    r.g54 = near.g54;
    r.covered = near.covered;
    r.far53 = chosen.g53;
    r.far54 = chosen.g54;
    r.pieces = g.n;
    r.roomWidth = box.x1 - box.x0 + 1;
    r.roomHeight = box.y1 - box.y0 + 1;
    r.roomDepth = box.z1 - box.z0 + 1;
    r.bottom = box.y0;
    r.originX = origin.x;
    r.originZ = origin.z;
    r.corridorGain = chosen.g54 - chosen.withoutCorridor;
    r.hutWidth = 7;
    r.regionMask = regionMask;
    r.orderedGain = chosen.ordered;
    r.bridgeColumns = chosen.bridges;
    r.deepCorridorGain = chosen.g54 - chosen.withoutDeep;
  }
}

#include <map>
struct QualificationWorkspace {
  uint64_t *targets = nullptr;
  int *counts = nullptr;
  mine26::Layout *layouts = nullptr;
  LayoutCandidate *results = nullptr;
  int *eligible = nullptr;
  int *eligibleCount = nullptr;
  RegionScore *scores = nullptr;
  int inputCapacity = 0, outputCapacity = 0;
  size_t scoreCapacity = 0;
  bool stackReady = false;
};
static std::map<int, QualificationWorkspace> qualificationWorkspaces;
static void clearQualificationWorkspace(QualificationWorkspace &w) {
  cudaFree(w.targets);
  cudaFree(w.counts);
  cudaFree(w.layouts);
  cudaFree(w.results);
  cudaFree(w.eligible);
  cudaFree(w.eligibleCount);
  cudaFree(w.scores);
  w = QualificationWorkspace{};
}
extern "C" int release_layout_qualification(int device) {
  auto e = cudaSetDevice(device);
  if (e != cudaSuccess)
    return int(e);
  auto entry = qualificationWorkspaces.find(device);
  if (entry != qualificationWorkspaces.end()) {
    clearQualificationWorkspace(entry->second);
    qualificationWorkspaces.erase(entry);
  }
  return 0;
}
extern "C" int qualify_layout_targets(int device, const uint64_t *targets,
                                      int n, int minimum, int minimumOrdered,
                                      LayoutCandidate *out, int cap,
                                      int *counts) {
  if (n < 1 || n > 262144)
    return -1;
  cudaError_t e = cudaSetDevice(device);
  if (e != cudaSuccess)
    return int(e);
  auto &w = qualificationWorkspaces[device];
  int eligibleCount = 0;
#define EVAL_CHECK(call)                                                       \
  if ((e = (call)) != cudaSuccess)                                             \
  goto done
  if (!w.stackReady) {
    EVAL_CHECK(cudaDeviceSetLimit(cudaLimitStackSize, 16384));
    w.stackReady = true;
  }
  if (n > w.inputCapacity) {
    w.inputCapacity = 0;
    cudaFree(w.targets);
    w.targets = nullptr;
    cudaFree(w.layouts);
    w.layouts = nullptr;
    cudaFree(w.eligible);
    w.eligible = nullptr;
    EVAL_CHECK(cudaMalloc(&w.targets, size_t(n) * sizeof(uint64_t)));
    EVAL_CHECK(cudaMalloc(&w.layouts, size_t(n) * sizeof(mine26::Layout)));
    EVAL_CHECK(cudaMalloc(&w.eligible, size_t(n) * sizeof(int)));
    w.inputCapacity = n;
  }
  if (cap > w.outputCapacity) {
    w.outputCapacity = 0;
    cudaFree(w.results);
    w.results = nullptr;
    EVAL_CHECK(cudaMalloc(&w.results, size_t(cap) * sizeof(LayoutCandidate)));
    w.outputCapacity = cap;
  }
  if (!w.counts)
    EVAL_CHECK(cudaMalloc(&w.counts, 4 * sizeof(int)));
  if (!w.eligibleCount)
    EVAL_CHECK(cudaMalloc(&w.eligibleCount, sizeof(int)));
  EVAL_CHECK(cudaMemcpy(w.targets, targets, size_t(n) * sizeof(uint64_t),
                        cudaMemcpyHostToDevice));
  {
    unsigned long long zero[5] = {};
    EVAL_CHECK(cudaMemcpyToSymbol(TARGET_STATS, zero, sizeof(zero)));
  }
  {
    unsigned zero = 0;
    EVAL_CHECK(cudaMemcpyToSymbol(OVERFLOW_COUNT, &zero, 4));
  }
  EVAL_CHECK(cudaMemset(w.counts, 0, 4 * sizeof(int)));
  EVAL_CHECK(cudaMemset(w.eligibleCount, 0, sizeof(int)));
  generateEligible<<<(n + 63) / 64, 64>>>(w.targets, n, w.layouts, w.eligible,
                                          w.eligibleCount, w.counts);
  EVAL_CHECK(cudaGetLastError());
  EVAL_CHECK(cudaMemcpy(&eligibleCount, w.eligibleCount, sizeof(int),
                        cudaMemcpyDeviceToHost));
  if (eligibleCount) {
    size_t needed = size_t(eligibleCount) * REGION_COUNT;
    if (needed > w.scoreCapacity) {
      size_t capacity =
          needed > w.scoreCapacity * 2 ? needed : w.scoreCapacity * 2;
      w.scoreCapacity = 0;
      cudaFree(w.scores);
      w.scores = nullptr;
      EVAL_CHECK(cudaMalloc(&w.scores, capacity * sizeof(RegionScore)));
      w.scoreCapacity = capacity;
    }
    scoreRegions<<<dim3(eligibleCount, REGION_COUNT), 64>>>(
        w.layouts, w.eligible, w.scores);
    EVAL_CHECK(cudaGetLastError());
    assembleCandidates<<<(eligibleCount + 63) / 64, 64>>>(
        w.targets, w.layouts, w.eligible, eligibleCount, w.scores, minimum,
        minimumOrdered, w.results, cap, w.counts);
    EVAL_CHECK(cudaGetLastError());
  }
  EVAL_CHECK(
      cudaMemcpy(counts, w.counts, 4 * sizeof(int), cudaMemcpyDeviceToHost));
  if (counts[2] > cap) {
    e = cudaErrorInvalidValue;
    goto done;
  }
  if (counts[2])
    EVAL_CHECK(cudaMemcpy(out, w.results,
                          size_t(counts[2]) * sizeof(LayoutCandidate),
                          cudaMemcpyDeviceToHost));
done:
  if (e != cudaSuccess)
    clearQualificationWorkspace(w);
  return int(e);
#undef EVAL_CHECK
}

extern "C" int target_stats(int device, unsigned long long *out) {
  auto e = cudaSetDevice(device);
  if (e != cudaSuccess)
    return e;
  return cudaMemcpyFromSymbol(out, TARGET_STATS, sizeof(TARGET_STATS));
}

extern "C" int layout_overflows(int device, uint64_t *out, int capacity,
                                unsigned *count) {
  auto e = cudaSetDevice(device);
  if (e != cudaSuccess)
    return e;
  e = cudaMemcpyFromSymbol(count, OVERFLOW_COUNT, 4);
  if (e != cudaSuccess)
    return e;
  if (*count > 4096 || *count > unsigned(capacity))
    return -1;
  return cudaMemcpyFromSymbol(out, OVERFLOW_TARGETS, *count * sizeof(uint64_t));
}
