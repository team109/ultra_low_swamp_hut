#include "layout_coordinate_regions.h"
#include "mine_inverse_types.cuh"
#ifndef ANISO_Z_MIN
#define ANISO_Z_MIN 0
#endif
#ifndef ANISO_Z_MAX
#define ANISO_Z_MAX 30000000
#endif
#ifdef HUNT_TRIAL_L1_RADIUS
__device__ bool nearTrialStart(uint64_t seed, int hx, int hz, int width) {
  int x = hx + width / 2, z = hz + (63 / width) / 2,
      region = HUNT_TRIAL_SPACING * 16;
  int margin = HUNT_TRIAL_L1_RADIUS + HUNT_TRIAL_HALF_SIZE + 16;
  for (int rz = floorDiv(z - margin, region);
       rz <= floorDiv(z + margin, region); rz++)
    for (int rx = floorDiv(x - margin, region);
         rx <= floorDiv(x + margin, region); rx++) {
      LCG r;
      r.seed(seed + uint64_t(int64_t(rx)) * 341873128712ULL +
             uint64_t(int64_t(rz)) * 132897987541ULL + HUNT_TRIAL_SALT);
      int cx = rx * HUNT_TRIAL_SPACING + r.integer(HUNT_TRIAL_SPREAD),
          cz = rz * HUNT_TRIAL_SPACING + r.integer(HUNT_TRIAL_SPREAD);
      r.large(seed, cx, cz);
      r.integer(HUNT_TRIAL_HEIGHT_SPAN);
      int rotation = r.integer(4);
      int ax =
          cx * 16 + ((rotation == 1 || rotation == 2) ? -HUNT_TRIAL_HALF_SIZE
                                                      : HUNT_TRIAL_HALF_SIZE);
      int az =
          cz * 16 + ((rotation == 2 || rotation == 3) ? -HUNT_TRIAL_HALF_SIZE
                                                      : HUNT_TRIAL_HALF_SIZE);
      int dx = ax - x, dz = az - z;
      if ((dx < 0 ? -dx : dx) + (dz < 0 ? -dz : dz) <= HUNT_TRIAL_L1_RADIUS)
        return true;
    }
  return false;
}
#endif
// Canonical hut seed = moveStructure(seed,-regionX,-regionZ).
// Low bits of its first two LCG draws prune the joint mine/hut solve early.
// The first four solved seed bits depend only on u/v modulo16 and the
// free low16 bits. Reuse these states across the full coordinate domain.
__global__ void generalPrefixTable(const MineTemplate *templates, int nt, int k,
                                   unsigned char *table) {
  int branches = 1 << (16 - k);
  uint64_t i = uint64_t(blockIdx.x) * blockDim.x + threadIdx.x,
           n = uint64_t(nt) * 256 * branches;
  if (i >= n)
    return;
  int free = i & (branches - 1);
  uint64_t cell = i >> (16 - k);
  int v = cell & 15, u = (cell >> 4) & 15;
  auto t = templates[cell >> 8];
  constexpr uint32_t A = uint32_t(0x5deece66dULL), B = 11,
                     A2 = uint32_t(uint64_t(A) * A),
                     B2 = uint32_t(uint64_t(A) * B + B),
                     A4 = uint32_t(uint64_t(A2) * A2),
                     B4 = uint32_t(uint64_t(A2) * B2 + B2);
  uint32_t seed =
      uint32_t(t.target & ((1ULL << k) - 1)) | (uint32_t(free) << k);
#pragma unroll
  for (int j = 16; j < 20; j++) {
    uint32_t a = (seed ^ A) * A2 + B2, b = (seed ^ A) * A4 + B4,
             f = (seed >> k) ^ (uint32_t(u) * (a >> 16)) ^
                 (uint32_t(v) * (b >> 16));
    seed |= ((f ^ uint32_t(t.target >> k)) >> (j - 16) & 1) << j;
  }
  table[i] = seed >> 16;
}
template <int K>
__global__ void mapGeneral(const MineTemplate *templates,
                           const unsigned char *prefix, int nt, int runtimeK,
                           int radius, int minimum, int maxU, uint64_t begin,
                           uint64_t n, MappedMine *out, int cap, int *count) {
  const int k = K ? K : runtimeK;
  uint64_t idx = begin + uint64_t(blockIdx.x) * blockDim.x + threadIdx.x;
  if (idx >= begin + n)
    return;
  int span = maxU - minimum + 1, sideU = 2 * span, sideV = 2 * radius + 1,
      branches = 1 << (16 - k);
  uint64_t cell = idx / branches;
  int free = idx % branches, vi = cell % sideV, ui = (cell / sideV) % sideU,
      v = vi - radius, u = ui < span ? -maxU + ui : minimum + ui - span,
      ti = cell / (uint64_t(sideU) * sideV);
  if (ti >= nt || !((u ^ v) & 1))
    return;
  // The signed intervals both contain zero when the domain includes X=0.
  // Keep its positive-side entry so every coordinate is visited once.
  if (minimum == 0 && ui == span - 1)
    return;
  int candidateZ = v * (16 << k);
  if (candidateZ < 0)
    candidateZ = -candidateZ;
  if (candidateZ < ANISO_Z_MIN || candidateZ >= ANISO_Z_MAX)
    return;
  int cx = u * (1 << k), cz = v * (1 << k);
  auto t = templates[ti];
  int x = cx * 16 + t.relx, z = cz * 16 + t.relz,
      rx = floorDiv(x, HUT_SPACING * 16), rz = floorDiv(z, HUT_SPACING * 16),
      wantX = x / 16 - rx * HUT_SPACING, wantZ = z / 16 - rz * HUT_SPACING;
  if (wantX < 0 || wantX >= HUT_SPACING - HUT_SEPARATION || wantZ < 0 ||
      wantZ >= HUT_SPACING - HUT_SEPARATION)
    return;
#ifdef INVERSE_MIN_ABS_COORD
  // Keep the float-coordinate regime used by the layout prior. Exclude a
  // margin around precision boundaries, including negative-side crossings.
  if ((x < 0 ? -x : x) < INVERSE_MIN_ABS_COORD ||
      (z < 0 ? -z : z) < INVERSE_MIN_ABS_COORD)
    return;
#endif
  constexpr uint64_t mask = (1ULL << 48) - 1, A = 0x5deece66dULL, B = 11,
                     A2 = A * A & mask, B2 = (A * B + B) & mask,
                     A4 = A2 * A2 & mask, B4 = (A2 * B2 + B2) & mask;
  uint64_t seed = (t.target & ((1ULL << k) - 1)) | (uint64_t(free) << k),
           shift = uint64_t(int64_t(rx)) * 341873128712ULL +
                   uint64_t(int64_t(rz)) * 132897987541ULL + HUT_SALT;
  seed |=
      uint64_t(
          prefix[(uint64_t(ti) * 256 + ((u & 15) * 16 + (v & 15))) * branches +
                 free])
      << 16;
  uint32_t early = (uint32_t(seed + shift) ^ uint32_t(A)) * uint32_t(A) + B,
           early2 = early * uint32_t(A) + B;
  if (((early >> 17) & 7) != (wantX & 7) || ((early2 >> 17) & 7) != (wantZ & 7))
    return;
#pragma unroll 28
  for (int j = 20; j < 48; j++) {
    uint64_t s = seed ^ A, a = (s * A2 + B2) & mask, b = (s * A4 + B4) & mask;
    uint32_t f = uint32_t(seed >> k) ^ (uint32_t(u) * uint32_t(a >> 16)) ^
                 (uint32_t(v) * uint32_t(b >> 16));
    seed |= ((uint64_t(f) ^ (t.target >> k)) >> (j - 16) & 1ULL) << j;
    if (j >= 17 && j <= 19) {
      uint64_t h = ((seed + shift) ^ A) * A + B, h2 = h * A + B;
      int m = (1 << (j - 16)) - 1;
      if (((h >> 17) & m) != (wantX & m) || ((h2 >> 17) & m) != (wantZ & m))
        return;
    }
  }
  LCG r;
  r.large(seed, cx, cz);
  if ((r.s ^ A) != t.target)
    return;
  int hx, hz;
  hutPosition(seed, rx, rz, hx, hz);
  if (hx != x || hz != z)
    return;
  r.large(seed, x / 16, z / 16);
  int width = (r.integer(4) & 1) ? 9 : 7;
  if (width != t.width)
    return;
#ifdef HUNT_TRIAL_L1_RADIUS
  if (nearTrialStart(seed, x, z, width))
    return;
#endif
  int p = atomicAdd(count, 1);
  if (p < cap)
    out[p] = {seed, cx, cz, x, z, width, t.g53, t.g54, t.covered, t.pieces, ti};
}

#include <algorithm>
#include <cstring>
#include <vector>
struct HutCellDescriptor {
  uint64_t cell, rangeBegin, shift;
  int u, v, cx, cz, x, z, rx, rz, ti, bucket;
};
struct HutFirstCache {
  int k = -1, nt = 0, cap = 0, stride = 0, prefixK = -1;
  unsigned char *prefix = nullptr;
  size_t prefixCapacity = 0;
  std::vector<MineTemplate> templates;
  MineTemplate *dt = nullptr;
  MappedMine *dr = nullptr;
  int *dc = nullptr;
  uint32_t *seeds = nullptr;
  int *counts = nullptr;
  HutCellDescriptor *cells = nullptr;
  uint64_t cellCapacity = 0;
  int *cellCount = nullptr;
  std::vector<MineTemplate> regionTemplates;
  std::vector<uint16_t> hostRegionMasks;
  uint16_t *regionMasks = nullptr;
};
static HutFirstCache caches[8];
extern "C" int mine_set_coordinate_regions(int device,
                                           const MineTemplate *templates,
                                           int nt, const uint16_t *masks) {
  if (device < 0 || device > 7 || nt < 0)
    return -1;
  auto e = cudaSetDevice(device);
  if (e != cudaSuccess)
    return int(e);
  auto &c = caches[device];
  if (nt == 0) {
    cudaFree(c.regionMasks);
    c.regionMasks = nullptr;
    c.regionTemplates.clear();
    c.hostRegionMasks.clear();
    return 0;
  }
  for (int i = 0; i < nt; i++)
    if ((masks[i] & ~511u) || templates[i].relx % 16 || templates[i].relz % 16)
      return -1;
  cudaFree(c.regionMasks);
  c.regionMasks = nullptr;
  c.regionTemplates.clear();
  c.hostRegionMasks.clear();
  e = cudaMalloc(&c.regionMasks, size_t(nt) * sizeof(uint16_t));
  if (e != cudaSuccess)
    return int(e);
  e = cudaMemcpy(c.regionMasks, masks, size_t(nt) * sizeof(uint16_t),
                 cudaMemcpyHostToDevice);
  if (e != cudaSuccess)
    return int(e);
  c.regionTemplates.assign(templates, templates + nt);
  c.hostRegionMasks.assign(masks, masks + nt);
  return 0;
}

// The union bounds are conservative for signed precision boundaries and
// template offsets. Exact per-template region checks preserve internal holes.
struct GeneralCoordinateBounds {
  int minimum, maxU;
};
static GeneralCoordinateBounds
generalBoundsForMasks(const MineTemplate *templates, int nt, int k, int radius,
                      const uint16_t *masks) {
  const int64_t stride = int64_t(16) * (1 << k);
  int64_t lower = ANISO_X_MIN, upper = ANISO_X_MAX;
  if (masks) {
    int64_t unionLower = INT64_MAX, unionUpper = 0;
    for (int i = 0; i < nt; i++) {
      int64_t offset = templates[i].relx;
      if (offset < 0)
        offset = -offset;
      for (int precision = 0; precision < 3; precision++)
        if (masks[i] & (7u << (3 * precision))) {
          int64_t classLower =
              precision == 0 ? 0 : (int64_t(1) << (22 + precision));
          int64_t classUpper =
              precision == 2 ? int64_t(ANISO_X_MAX)
                             : (int64_t(1) << (23 + precision)) + 1 + offset;
          int64_t candidateLower =
              classLower > offset ? classLower - offset : 0;
          if (candidateLower < unionLower)
            unionLower = candidateLower;
          if (classUpper > unionUpper)
            unionUpper = classUpper;
        }
    }
    if (unionLower == INT64_MAX)
      return {1, 0};
    if (unionLower > lower)
      lower = unionLower;
    if (unionUpper < upper)
      upper = unionUpper;
  }
  if (upper <= lower)
    return {1, 0};
  int minimum = int((lower + stride - 1) / stride),
      maxU = int((upper - 1) / stride);
  if (maxU > radius)
    maxU = radius;
  return {minimum, maxU};
}
static GeneralCoordinateBounds generalBounds(const MineTemplate *templates,
                                             int nt, int k, int radius,
                                             int device) {
  const uint16_t *masks = nullptr;
  if (device >= 0 && device < 8) {
    auto &c = caches[device];
    if (c.regionTemplates.size() == size_t(nt) &&
        c.hostRegionMasks.size() == size_t(nt) &&
        !std::memcmp(c.regionTemplates.data(), templates,
                     size_t(nt) * sizeof(MineTemplate)))
      masks = c.hostRegionMasks.data();
  }
  return generalBoundsForMasks(templates, nt, k, radius, masks);
}
extern "C" uint64_t mine_general_cases(const MineTemplate *templates, int nt,
                                       int k, int radius) {
  if (nt < 1 || k < 0 || k > 15 || radius < 0)
    return 0;
  int device = -1;
  cudaGetDevice(&device);
  auto bounds = generalBounds(templates, nt, k, radius, device);
  if (bounds.maxU < bounds.minimum)
    return 0;
  return uint64_t(nt) * 2 * (bounds.maxU - bounds.minimum + 1) *
         (uint64_t(2) * radius + 1) * (1ULL << (16 - k));
}

template <int K>
__global__ void
buildHutCells(const MineTemplate *templates, int nt, int runtimeK, int radius,
              int minimum, int maxU, uint64_t begin, uint64_t firstCell,
              uint64_t cellsPerRange, uint64_t caseStride, int rangeCount,
              HutCellDescriptor *out, int *count, const uint16_t *regionMasks) {
  constexpr int k = K;
  uint64_t index = uint64_t(blockIdx.x) * blockDim.x + threadIdx.x;
  if (index >= cellsPerRange * rangeCount)
    return;
  uint64_t range = index / cellsPerRange;
  uint64_t cell = firstCell + index % cellsPerRange +
                  range * (caseStride / (1ULL << (16 - k)));
  uint64_t rangeBegin = begin + range * caseStride;
  int span = maxU - minimum + 1, sideU = 2 * span, sideV = 2 * radius + 1;
  int vi = cell % sideV, ui = (cell / sideV) % sideU;
  int v = vi - radius, u = ui < span ? -maxU + ui : minimum + ui - span;
  int ti = cell / (uint64_t(sideU) * sideV);
  if (ti >= nt || !((u ^ v) & 1))
    return;
  if (minimum == 0 && ui == span - 1)
    return;
  int candidateZ = v * (16 << k);
  if (candidateZ < 0)
    candidateZ = -candidateZ;
  if (candidateZ < ANISO_Z_MIN || candidateZ >= ANISO_Z_MAX)
    return;
  auto t = templates[ti];
  int cx = u * (1 << k), cz = v * (1 << k), x = cx * 16 + t.relx,
      z = cz * 16 + t.relz;
  if (regionMasks && !(regionMasks[ti] &
                       (1u << layout_coordinates::coordinateRegionIndex(x, z))))
    return;
  int rx = floorDiv(x, HUT_SPACING * 16), rz = floorDiv(z, HUT_SPACING * 16);
  int wantX = x / 16 - rx * HUT_SPACING, wantZ = z / 16 - rz * HUT_SPACING;
  if (wantX < 0 || wantX >= HUT_SPACING - HUT_SEPARATION || wantZ < 0 ||
      wantZ >= HUT_SPACING - HUT_SEPARATION)
    return;
  uint64_t shift = uint64_t(int64_t(rx)) * 341873128712ULL +
                   uint64_t(int64_t(rz)) * 132897987541ULL + HUT_SALT;
  int bucket = (((wantX & 7) * 8 + (wantZ & 7)) << k) |
               ((t.target + shift) & ((1 << k) - 1));
  int outputIndex = atomicAdd(count, 1);
  out[outputIndex] = {cell, rangeBegin, shift, u,  v,  cx,    cz,
                      x,    z,          rx,    rz, ti, bucket};
}

template <int K>
__global__ void
mapHutFirst(const MineTemplate *templates, int runtimeK, uint64_t n,
            const uint32_t *seeds, const int *counts, int stride,
            const HutCellDescriptor *descriptors, int descriptorCount,
            const unsigned char *prefix, MappedMine *out, int cap, int *count) {
  constexpr int k = K;
  int descriptorIndex = blockIdx.x,
      choice = blockIdx.y * blockDim.x + threadIdx.x;
  if (descriptorIndex >= descriptorCount || choice >= stride)
    return;
  auto d = descriptors[descriptorIndex];
  int u = d.u, v = d.v, cx = d.cx, cz = d.cz, x = d.x, z = d.z, rx = d.rx,
      rz = d.rz, ti = d.ti, bucket = d.bucket;
  uint64_t cell = d.cell, begin = d.rangeBegin, shift = d.shift;
  int branches = 1 << (16 - k);
  auto t = templates[ti];
  constexpr uint64_t mask = (1ULL << 48) - 1, A = 0x5deece66dULL, B = 11,
                     A2 = A * A & mask, B2 = (A * B + B) & mask,
                     A4 = A2 * A2 & mask, B4 = (A2 * B2 + B2) & mask;
  if (choice >= counts[bucket])
    return;
  uint64_t seed =
      (uint64_t(seeds[uint64_t(bucket) * stride + choice]) - shift) &
      ((1 << 20) - 1);
  int free = (seed >> k) & (branches - 1);
  uint64_t oldIndex = cell * branches + free;
  if (oldIndex < begin || oldIndex >= begin + n)
    return;
  // Reuse the target-specific four-bit lift for this coordinate residue.
  uint64_t prefixIndex =
      (uint64_t(ti) * 256 + ((u & 15) * 16 + (v & 15))) * branches + free;
  if ((seed >> 16) != prefix[prefixIndex])
    return;
  // Only bits16..47 of the LCG images enter the lifting equation.
  // Each changed seed bit is>=20, so low16 of either image stays fixed.
  uint32_t a = uint32_t((((seed ^ A) * A2 + B2) & mask) >> 16);
  uint32_t b = uint32_t((((seed ^ A) * A4 + B4) & mask) >> 16);
#pragma unroll 28
  for (int j = 20; j < 48; j++) {
    uint32_t f = uint32_t(seed >> k) ^ (uint32_t(u) * a) ^ (uint32_t(v) * b);
    uint32_t bit =
        uint32_t(((uint64_t(f) ^ (t.target >> k)) >> (j - 16)) & 1ULL);
    seed |= uint64_t(bit) << j;
    uint32_t deltaA = ((A >> j) & 1ULL) ? -(uint32_t(A2) << (j - 16))
                                        : (uint32_t(A2) << (j - 16));
    uint32_t deltaB = ((A >> j) & 1ULL) ? -(uint32_t(A4) << (j - 16))
                                        : (uint32_t(A4) << (j - 16));
    a += (0U - bit) & deltaA;
    b += (0U - bit) & deltaB;
  }
  LCG r;
  r.large(seed, cx, cz);
  if ((r.s ^ A) != t.target)
    return;
  int hx, hz;
  hutPosition(seed, rx, rz, hx, hz);
  if (hx != x || hz != z)
    return;
  r.large(seed, x / 16, z / 16);
  int width = (r.integer(4) & 1) ? 9 : 7;
  if (width != t.width)
    return;
#ifdef HUNT_TRIAL_L1_RADIUS
  if (nearTrialStart(seed, x, z, width))
    return;
#endif
  int p = atomicAdd(count, 1);
  if (p < cap)
    out[p] = {seed, cx, cz, x, z, width, t.g53, t.g54, t.covered, t.pieces, ti};
}
extern "C" int mine_map_hutfirst_strided(int device,
                                         const MineTemplate *templates, int nt,
                                         int k, int radius, uint64_t begin,
                                         uint64_t n, MappedMine *out, int cap,
                                         int *count, uint64_t caseStride,
                                         int rangeCount) {
  if (rangeCount < 1 || rangeCount > 64 || caseStride % (1ULL << (16 - k)))
    return -1;
  if (device < 0 || device > 7 || nt < 1 || k < 0 || k > 5 || n < 1 ||
      n > 268435456 || cap < 1)
    return -1;
  auto e = cudaSetDevice(device);
  if (e != cudaSuccess)
    return int(e);
  auto &c = caches[device];
  auto bounds = generalBounds(templates, nt, k, radius, device);
  int minimum = bounds.minimum, maxU = bounds.maxU;
  if (maxU < minimum) {
    *count = 0;
    return 0;
  }
#define HF(call)                                                               \
  if ((e = (call)) != cudaSuccess)                                             \
  return int(e)
  if (c.k != k) {
    cudaFree(c.seeds);
    cudaFree(c.counts);
    c.seeds = nullptr;
    c.counts = nullptr;
    c.k = -1;
    std::vector<int> counts(64 * (1 << k));
    std::vector<std::vector<uint32_t>> buckets(counts.size());
    constexpr uint64_t A = 0x5deece66dULL, M = (1 << 20) - 1;
    for (uint32_t seed = 0; seed <= M; seed++) {
      uint64_t h = ((seed ^ A) * A + 11) & M, h2 = (h * A + 11) & M;
      int bucket = ((((h >> 17) & 7) * 8 + ((h2 >> 17) & 7)) << k) |
                   (seed & ((1 << k) - 1));
      buckets[bucket].push_back(seed);
    }
    c.stride = 0;
    for (size_t b = 0; b < buckets.size(); b++) {
      counts[b] = buckets[b].size();
      c.stride = std::max(c.stride, counts[b]);
    }
    std::vector<uint32_t> table(uint64_t(counts.size()) * c.stride);
    for (size_t b = 0; b < buckets.size(); b++)
      std::copy(buckets[b].begin(), buckets[b].end(),
                table.begin() + b * c.stride);
    HF(cudaMalloc(&c.seeds, table.size() * sizeof(uint32_t)));
    HF(cudaMalloc(&c.counts, counts.size() * sizeof(int)));
    HF(cudaMemcpy(c.seeds, table.data(), table.size() * sizeof(uint32_t),
                  cudaMemcpyHostToDevice));
    HF(cudaMemcpy(c.counts, counts.data(), counts.size() * sizeof(int),
                  cudaMemcpyHostToDevice));
    c.k = k;
  }
  if (c.nt != nt || c.templates.size() != size_t(nt) ||
      std::memcmp(c.templates.data(), templates, nt * sizeof(MineTemplate))) {
    cudaFree(c.dt);
    c.dt = nullptr;
    HF(cudaMalloc(&c.dt, nt * sizeof(MineTemplate)));
    HF(cudaMemcpy(c.dt, templates, nt * sizeof(MineTemplate),
                  cudaMemcpyHostToDevice));
    c.templates.assign(templates, templates + nt);
    c.nt = nt;
    c.prefixK = -1;
  }
  if (c.prefixK != k) {
    size_t length = size_t(nt) * 256 * (1u << (16 - k));
    if (c.prefixCapacity < length) {
      cudaFree(c.prefix);
      c.prefix = nullptr;
      c.prefixCapacity = 0;
      HF(cudaMalloc(&c.prefix, length));
      c.prefixCapacity = length;
    }
    generalPrefixTable<<<(length + 127) / 128, 128>>>(c.dt, nt, k, c.prefix);
    HF(cudaGetLastError());
    c.prefixK = k;
  }
  if (c.cap < cap) {
    cudaFree(c.dr);
    c.dr = nullptr;
    HF(cudaMalloc(&c.dr, cap * sizeof(MappedMine)));
    c.cap = cap;
  }
  if (!c.dc)
    HF(cudaMalloc(&c.dc, sizeof(int)));
  HF(cudaMemset(c.dc, 0, sizeof(int)));
  uint64_t branches = 1ULL << (16 - k), first = begin / branches,
           cells = (begin + n - 1) / branches - first + 1;
  uint64_t work = cells * rangeCount;
  if (c.cellCapacity < work) {
    cudaFree(c.cells);
    c.cells = nullptr;
    HF(cudaMalloc(&c.cells, work * sizeof(HutCellDescriptor)));
    c.cellCapacity = work;
  }
  if (!c.cellCount)
    HF(cudaMalloc(&c.cellCount, sizeof(int)));
  HF(cudaMemset(c.cellCount, 0, sizeof(int)));
  const uint16_t *regionMasks =
      c.regionTemplates.size() == size_t(nt) &&
              !std::memcmp(c.regionTemplates.data(), templates,
                           nt * sizeof(MineTemplate))
          ? c.regionMasks
          : nullptr;
#define BUILD_CELLS(K)                                                         \
  buildHutCells<K><<<(work + 127) / 128, 128>>>(                               \
      c.dt, nt, k, radius, minimum, maxU, begin, first, cells, caseStride,     \
      rangeCount, c.cells, c.cellCount, regionMasks)
  switch (k) {
  case 0:
    BUILD_CELLS(0);
    break;
  case 1:
    BUILD_CELLS(1);
    break;
  case 2:
    BUILD_CELLS(2);
    break;
  case 3:
    BUILD_CELLS(3);
    break;
  case 4:
    BUILD_CELLS(4);
    break;
  case 5:
    BUILD_CELLS(5);
    break;
  }
#undef BUILD_CELLS
  HF(cudaGetLastError());
  int descriptorCount = 0;
  HF(cudaMemcpy(&descriptorCount, c.cellCount, sizeof(int),
                cudaMemcpyDeviceToHost));
  if (descriptorCount) {
    dim3 grid(descriptorCount, (c.stride + 127) / 128);
#define LAUNCH(K)                                                              \
  mapHutFirst<K><<<grid, 128>>>(c.dt, k, n, c.seeds, c.counts, c.stride,       \
                                c.cells, descriptorCount, c.prefix, c.dr, cap, \
                                c.dc)
    switch (k) {
    case 0:
      LAUNCH(0);
      break;
    case 1:
      LAUNCH(1);
      break;
    case 2:
      LAUNCH(2);
      break;
    case 3:
      LAUNCH(3);
      break;
    case 4:
      LAUNCH(4);
      break;
    case 5:
      LAUNCH(5);
      break;
    }
#undef LAUNCH
  }
  HF(cudaGetLastError());
  HF(cudaMemcpy(count, c.dc, sizeof(int), cudaMemcpyDeviceToHost));
  if (*count > cap)
    return -2;
  HF(cudaMemcpy(out, c.dr, size_t(*count) * sizeof(MappedMine),
                cudaMemcpyDeviceToHost));
  return 0;
#undef HF
}

extern "C" int mine_map_hutfirst(int device, const MineTemplate *templates,
                                 int nt, int k, int radius, uint64_t begin,
                                 uint64_t n, MappedMine *out, int cap,
                                 int *count) {
  return mine_map_hutfirst_strided(device, templates, nt, k, radius, begin, n,
                                   out, cap, count, 0, 1);
}
