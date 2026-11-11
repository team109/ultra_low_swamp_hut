// Focused heuristic cascade. Named scalar noises are exact; these gates are not
// an equivalent terrain generator. Thresholds come from the selected version
// profile.
#include "noise_gate_defaults.cuh"
#include "noise_seed26.cu"
#include <cstring>
#ifdef NC_SURFACE_GATE
#include "surface_helpers26.cuh"
#endif
#ifndef NC_THREADS
#define NC_THREADS 64
#endif
#ifdef NC_SHARED_PERMUTATIONS
__device__ __noinline__ unsigned char *permutationBank26() {
  __shared__ unsigned char bank[256 * NC_THREADS];
  return bank;
}
struct SharedPermutation26 {
  unsigned char *bank;
  // Pack four entries per thread into one shared-memory word. Every lane
  // owns a different bank even when lanes look up different permutation slots.
  __device__ unsigned char &operator[](int i) {
    return bank[((i >> 2) * NC_THREADS + threadIdx.x) * 4 + (i & 3)];
  }
  __device__ const unsigned char &operator[](int i) const {
    return bank[((i >> 2) * NC_THREADS + threadIdx.x) * 4 + (i & 3)];
  }
};
struct SharedLayer26 {
  double x, y, z;
  SharedPermutation26 perm;
};
#endif
#ifdef NC_DEEP_CHEESE
#define NC_NOISE_COUNT 15
#else
#define NC_NOISE_COUNT 14
#endif
struct Named {
  uint64_t a, b;
  int first, count;
#ifdef NC_FIXED_SEED
  Layer *cached = nullptr;
#endif
};
struct CascadeScratch26 {
  struct Allocation {
    void *data = nullptr;
    size_t capacity = 0;
  };
  std::vector<Allocation> allocations;
  size_t cursor = 0;
  void reset() { cursor = 0; }
  template <class T> cudaError_t allocate(T **pointer, size_t bytes) {
    if (cursor == allocations.size())
      allocations.emplace_back();
    auto &slot = allocations[cursor++];
    if (bytes > slot.capacity) {
      if (slot.data) {
        auto error = cudaFree(slot.data);
        if (error != cudaSuccess)
          return error;
        slot.data = nullptr;
        slot.capacity = 0;
      }
      auto error = cudaMalloc(&slot.data, bytes);
      if (error != cudaSuccess)
        return error;
      slot.capacity = bytes;
    }
    *pointer = static_cast<T *>(slot.data);
    return cudaSuccess;
  }
  ~CascadeScratch26() {
    for (auto &slot : allocations)
      if (slot.data)
        cudaFree(slot.data);
  }
};
template <class T>
static cudaError_t allocateCascade26(CascadeScratch26 *scratch, T **pointer,
                                     size_t bytes) {
  return scratch ? scratch->allocate(pointer, bytes)
                 : cudaMalloc(pointer, bytes);
}
static cudaError_t releaseCascade26(CascadeScratch26 *scratch, void *pointer) {
  return scratch ? cudaSuccess : cudaFree(pointer);
}
struct Cascade {
  int device;
  Named *names;
  SeedSpec *layers;
  CascadeScratch26 scratch;

#ifdef NC_FIXED_SEED
  Layer *cache = nullptr;
  int layerCount = 0;
  int *positions = nullptr;
  int positionCount = 0;
  uint64_t positionLow = 0;
  Named *batchNames = nullptr;
  Layer *batchCache = nullptr;
  unsigned char *batchOutput = nullptr;
  int batchCapacity = 0;
  size_t outputCapacity = 0;
#endif
};
#ifdef NC_COORDINATE_EROSION_BOUNDS
// A corner gradient uses two signed axes. Its absolute dot product is bounded
// by the two largest absolute offsets. Interpolation gives a bound using only
// the octave offsets, before constructing its 256-entry permutation.
__device__ double gradientEnvelope26(double xx, double yy, double zz, double px,
                                     double py, double pz) {
  double x = wrap(xx) + px, y = wrap(yy) + py, z = wrap(zz) + pz;
  float fx = float(x - floor(x)), fy = float(y - floor(y)),
        fz = float(z - floor(z));
  double a = fmin(1., fmax(0., double(smoothf(fx)))),
         b = fmin(1., fmax(0., double(smoothf(fy)))),
         c = fmin(1., fmax(0., double(smoothf(fz))));
  double sum = 0;
  for (int dz = 0; dz < 2; dz++)
    for (int dy = 0; dy < 2; dy++)
      for (int dx = 0; dx < 2; dx++) {
        double u = fabs(double(fx) - dx), v = fabs(double(fy) - dy),
               w = fabs(double(fz) - dz);
        sum += (dx ? a : 1 - a) * (dy ? b : 1 - b) * (dz ? c : 1 - c) *
               (u + v + w - fmin(u, fmin(v, w)));
      }
  return sum + 1e-5; // Scalar float evaluation and interpolation rounding.
}
__device__ double octaveEnvelope26(const SeedSpec &q, const uint64_t *banks,
                                   const double *xyz) {
  XR r = xr2(banks[2 * q.bank] ^ q.a, banks[2 * q.bank + 1] ^ q.b);
  double px = double(next64(r) >> 11) * 0x1p-53 * 256.,
         py = double(next64(r) >> 11) * 0x1p-53 * 256.,
         pz = double(next64(r) >> 11) * 0x1p-53 * 256.;
  return fabs(double(q.amplitude)) *
         gradientEnvelope26(xyz[0] * q.frequency, xyz[1] * q.frequency,
                            xyz[2] * q.frequency, px, py, pz);
}
#endif
__device__ void samples26(uint64_t seed, int id, const Named *names,
                          const SeedSpec *layers, const double *xyz, int n,
                          float *out, double lower = -1e100) {
  Named name = names[id];
#ifdef NC_FIXED_SEED
  if (name.cached) {
    for (int i = 0; i < n; i++)
      out[i] = 0;
    for (int j = 0; j < name.count; j++) {
      SeedSpec q = layers[name.first + j];
      const Layer &p = name.cached[j];
      for (int i = 0; i < n; i++)
        out[i] += q.amplitude * perlin(p, xyz[3 * i] * q.frequency,
                                       xyz[3 * i + 1] * q.frequency,
                                       xyz[3 * i + 2] * q.frequency, false);
#ifdef NC_INTERVAL_EROSION
      if (lower > -1e90) {
        double remaining = 0;
        for (int k = j + 1; k < name.count; k++)
          remaining += fabs(double(layers[name.first + k].amplitude));
        if (double(out[0]) + 1.23 * remaining + 1e-5 < lower) {
          out[0] = -1e30f;
          return;
        }
      }
#endif
    }
    return;
  }
#endif
  uint64_t s = seed ^ 0x6a09e667f3bcc909ULL;
  XR world = xr2(mix64(s), mix64(s + 0x9e3779b97f4a7c15ULL));
  uint64_t a = next64(world), b = next64(world);
  XR named = xr2(a ^ name.a, b ^ name.b);
  uint64_t banks[4];
  for (int j = 0; j < 4; j++)
    banks[j] = next64(named);
  for (int i = 0; i < n; i++)
    out[i] = 0;
#ifdef NC_COORDINATE_EROSION_BOUNDS
  double suffix[65];
  if (lower > -1e90) {
    suffix[name.count] = 0;
    for (int j = name.count - 1; j >= 0; j--)
      suffix[j] =
          suffix[j + 1] + octaveEnvelope26(layers[name.first + j], banks, xyz);
    if (suffix[0] + 1e-5 < lower) {
      out[0] = -1e30f;
      return;
    }
  }
#endif
  for (int j = 0; j < name.count; j++) {
#ifdef NC_COORDINATE_EROSION_BOUNDS
    if (lower > -1e90 && double(out[0]) + suffix[j] + 1e-5 < lower) {
      out[0] = -1e30f;
      return;
    }
#endif
    SeedSpec q = layers[name.first + j];
    XR rng = xr2(banks[2 * q.bank] ^ q.a, banks[2 * q.bank + 1] ^ q.b);
#ifdef NC_SHARED_PERMUTATIONS
    SharedLayer26 p;
    p.perm.bank = permutationBank26();
#else
    Layer p;
#endif
    p.x = double(next64(rng) >> 11) * 0x1p-53 * 256.;
    p.y = double(next64(rng) >> 11) * 0x1p-53 * 256.;
    p.z = double(next64(rng) >> 11) * 0x1p-53 * 256.;
#ifdef NC_SHARED_PERMUTATIONS
    for (int k = 0; k < 64; k++)
      reinterpret_cast<unsigned int *>(
          p.perm.bank)[k * NC_THREADS + threadIdx.x] =
          0x03020100u + unsigned(k) * 0x04040404u;
#else
    for (int k = 0; k < 256; k++)
      p.perm[k] = k;
#endif
    for (int k = 0; k < 256; k++) {
      int v = k + bound32(rng, 256 - k);
      unsigned char t = p.perm[k];
      p.perm[k] = p.perm[v];
      p.perm[v] = t;
    }
    for (int i = 0; i < n; i++)
      out[i] += q.amplitude * perlin(p, xyz[3 * i] * q.frequency,
                                     xyz[3 * i + 1] * q.frequency,
                                     xyz[3 * i + 2] * q.frequency, false);
#ifdef NC_INTERVAL_EROSION
    if (lower > -1e90) {
      double remaining = 0;
      for (int k = j + 1; k < name.count; k++)
        remaining += fabs(double(layers[name.first + k].amplitude));
      // Gradient norm sqrt(2); quintic interpolation weights give E[r^2]<=3/4.
      // Thus exact |Perlin|<=sqrt(3/2). 1.23 and 1e-5 cover scalar FP rounding.
      if (double(out[0]) + 1.23 * remaining + 1e-5 < lower) {
        out[0] = -1e30f;
        return;
      }
    }
#endif
  }
}
#ifdef NC_FAST_ER
#ifndef NC_FAST_ER_MIN
#define NC_FAST_ER_MIN .40
#endif
__device__ void fastErosion26(uint64_t seed, const Named *n, const SeedSpec *l,
                              const double *xyz, float *out) {
#ifdef NC_FAST_ER_PREFIX_OCTAVES
  // Rebase the named noise while retaining its original octave amplitudes.
  // The complete shifted erosion predicate remains in screenPoint.
  Named erosion = n[1];
  erosion.count = NC_FAST_ER_PREFIX_OCTAVES;
  samples26(seed, 0, &erosion, l, xyz, 1, out, NC_FAST_ER_MIN);
#else
  samples26(seed, 1, n, l, xyz, 1, out, NC_FAST_ER_MIN);
#endif
}
#endif
__device__ double one26(uint64_t s, int id, const Named *n, const SeedSpec *l,
                        double x, double y, double z) {
  double xyz[3] = {x, y, z};
  float v;
  samples26(s, id, n, l, xyz, 1, &v);
  return v;
}
// names: offset, erosion, temperature, continentalness, ridge, floodedness,
// entrance, cheese, rarity, thickness, spaghetti1, spaghetti2, modulator,
// roughness.
__device__ double spaghetti26(uint64_t s, const Named *n, const SeedSpec *l,
                              double x, double y, double z) {
  double r = one26(s, 8, n, l, x * 2, y, z * 2), scale = r < -.5  ? .75
                                                         : r < 0  ? 1.
                                                         : r < .5 ? 1.5
                                                                  : 2.;
  double t = one26(s, 9, n, l, x, y, z),
         a = one26(s, 10, n, l, x / scale, y / scale, z / scale),
         b = one26(s, 11, n, l, x / scale, y / scale, z / scale);
  double m = one26(s, 12, n, l, x, y, z), q = one26(s, 13, n, l, x, y, z),
         thick = .065 + (t + 1) * .5 * (.088 - .065);
  return fmax(-1., fmin(1., fmax(fabs(scale * a) - thick,
                                 fabs(scale * b) - thick))) +
         (-.05 - .05 * m) * (-.4 + fabs(q));
}
// Cache the exact climate inputs when compacting after temperature.
struct StageCache26 {
  double sx, sz;
  float erosion;
  int index;
};
template <int PHASE = 0>
__device__ void screenPoint(uint64_t seed, int x, int z, const Named *n,
                            const SeedSpec *l, unsigned char *result,
                            bool prechecked = false,
                            StageCache26 *cache = nullptr) {
  unsigned char stage = PHASE == 2 ? 2 : 0;
  double xyz[33], sx = 0, sz = 0, er = 0;
  if constexpr (PHASE == 2) {
    sx = cache->sx;
    sz = cache->sz;
    er = cache->erosion;
  }
  if constexpr (PHASE != 2) {
#ifdef NC_FAST_ER
#ifndef NC_FAST_ER_MIN
#define NC_FAST_ER_MIN .40
#endif
    // Broad unshifted erosion prefilter for targeted discovery only, not a
    // bound.
    if (!prechecked) {
      double fastxyz[3] = {(x + 8) * .25, 0, (z + 8) * .25};
      float fast;
      fastErosion26(seed, n, l, fastxyz, &fast);
      if (fast < NC_FAST_ER_MIN) {
        *result = 0;
        return;
      }
    }
#endif
#define PASS(test)                                                             \
  if (!(test)) {                                                               \
    *result = stage;                                                           \
    return;                                                                    \
  }                                                                            \
  ++stage
    double cx = x + 8, cz = z + 8,
           shift[6] = {cx * .25, 0, cz * .25, cz * .25, cx * .25, 0};
    float offsets[2];
    samples26(seed, 0, n, l, shift, 2, offsets);
    sx = cx * .25 + 4. * offsets[0];
    sz = cz * .25 + 4. * offsets[1];
#ifdef NC_INTERVAL_EROSION
    double erxyz[3] = {sx, 0, sz};
    float erv;
    samples26(seed, 1, n, l, erxyz, 1, &erv, NC_EROSION_MIN);
    er = erv;
#else
    er = one26(seed, 1, n, l, sx, 0, sz);
#endif
    double v = er;
    PASS(v >= NC_EROSION_MIN);
#ifdef NC_SINGLE_BIOME
    // A fixed BiomeSource does not impose a temperature condition.
    PASS(true);
#else
    v = one26(seed, 2, n, l, sx, 0, sz);
    PASS(v >= NC_TEMPERATURE_MIN && v <= NC_TEMPERATURE_MAX);
#endif
  }
  if constexpr (PHASE == 1) {
    cache->sx = sx;
    cache->sz = sz;
    cache->erosion = er;
    *result = stage;
    return;
  }
  double v = er;
  double co = one26(seed, 3, n, l, sx, 0, sz);
  v = co;
  PASS(v >= NC_CONTINENTALNESS_MIN);
  v = one26(seed, 4, n, l, sx, 0, sz);
  PASS(fabs(v) <= NC_RIDGE_ABS_MAX ||
       (NC_RIDGE_ABSOLUTE ? fabs(v) : v) >= NC_RIDGE_OUTER_MIN);
#ifdef NC_SURFACE_GATE
  float sf[2];
  surfaceFactors26(float(co), float(er), float(v), sf);
  PASS(surfaceApprox26(sf[0], sf[1]) >= NC_SURFACE_DEPTH_MIN);

#endif
  int dy[5] = {60, 0, -53, 30, -30};
  float flood[5];
  {
    for (int j = 0; j < 5; j++) {
      xyz[j * 3] = x + 3;
      xyz[j * 3 + 1] = dy[j] * .67;
      xyz[j * 3 + 2] = z + 3;
    }
    samples26(seed, 5, n, l, xyz, 5, flood);
    for (int j = 0; j < 5; j++) {
      PASS(flood[j] <= NC_FLOODEDNESS_MAX);
    }
  }

#ifdef NC_LAZY_CAVES
  int heights[11] = {60, 50, 0, -53, -30, 30, -10, -40, 10, 40, 20};
  for (int j = 0; j < 11; j++) {
    int y = heights[j];
    double entry = one26(seed, 6, n, l, .75 * (x + 3), y * .5, .75 * (z + 3));
    if (j < 2) {
      PASS(entry < NC_ENTRANCE_MAX ||
           spaghetti26(seed, n, l, x + 3, y, z + 3) < .020001);
    } else {
      double bias = .37 + .3 * (1 - fmax(0., fmin(1., (y + 10) / 40.)));
      PASS(entry + bias < 0 ||
           one26(seed, 7, n, l, x + 3, y * (2. / 3.), z + 3) < NC_CHEESE_MAX ||
           spaghetti26(seed, n, l, x + 3, y, z + 3) < .000001);
    }
  }
#else
  int ys[11] = {60, 50, 0, -53, -30, 30, -10, -40, 10, 40, 20};
  float entrance[11], cheese[9];
  for (int j = 0; j < 11; j++) {
    xyz[j * 3] = .75 * (x + 3);
    xyz[j * 3 + 1] = ys[j] * .5;
    xyz[j * 3 + 2] = .75 * (z + 3);
  }
  samples26(seed, 6, n, l, xyz, 11, entrance);
  for (int j = 0; j < 2; j++) {
    PASS(entrance[j] < NC_ENTRANCE_MAX ||
         spaghetti26(seed, n, l, x + 3, ys[j], z + 3) < .020001);
  }
  for (int j = 0; j < 9; j++) {
    xyz[j * 3] = x + 3;
    xyz[j * 3 + 1] = ys[j + 2] * (2. / 3.);
    xyz[j * 3 + 2] = z + 3;
  }
  samples26(seed, 7, n, l, xyz, 9, cheese);
  for (int j = 0; j < 9; j++) {
    int y = ys[j + 2];
    double bias = .37 + .3 * (1 - fmax(0., fmin(1., (y + 10) / 40.)));
    PASS(double(entrance[j + 2]) + bias < 0 || cheese[j] < NC_CHEESE_MAX ||
         spaghetti26(seed, n, l, x + 3, y, z + 3) < .000001);
  }
#endif
#ifdef NC_DEEP_CHEESE
  // Target the deep cheese-cave path, including layer noise and the bottom
  // slide. The mineshaft supplies the opening below this pair of probes.
  for (int j = 0; j < 2; j++) {
    int y = j ? -40 : -48;
    double limit = j ? 0. : -.05859375;
    double cheese = one26(seed, 7, n, l, x + 3, y * (2. / 3.), z + 3);
    double layer = one26(seed, 14, n, l, x + 3, y * 8., z + 3);
    PASS(4 * layer * layer + fmax(-1., fmin(1., .27 + cheese)) < limit);
  }
#endif
  *result = stage;
#undef PASS
}
__global__ void cascade26(uint64_t low, const uint64_t *seeds, int count, int x,
                          int z, const Named *n, const SeedSpec *l,
                          unsigned char *stages, const uint64_t *lows,
                          const int *coords, const int *active) {
  int i = blockIdx.x * blockDim.x + threadIdx.x;
  if (i >= count)
    return;
  if (active)
    i = active[i];
  if (lows) {
    int group = i >> 16;
    low = lows[group];
    x = coords[group * 2];
    z = coords[group * 2 + 1];
    stages += group * 65536;
    i &= 65535;
  }
  uint64_t seed = seeds ? seeds[i] : (low | (uint64_t(i) << 48));
  screenPoint(seed, x, z, n, l, stages + i, active != nullptr);
}

#if defined(NC_COMPACT_FAST_ER) && defined(NC_FAST_ER)
__global__ void compactErosion(const uint64_t *lows, const int *coords,
                               int count, const Named *n, const SeedSpec *l,
                               int *active, int *selected) {
  int i = blockIdx.x * blockDim.x + threadIdx.x;
  if (i >= count)
    return;
  int group = i >> 16;
  uint64_t seed = lows[group] | (uint64_t(i & 65535) << 48);
  double xyz[3] = {(coords[2 * group] + 8) * .25, 0,
                   (coords[2 * group + 1] + 8) * .25};
  float value;
  fastErosion26(seed, n, l, xyz, &value);
  bool pass = value >= NC_FAST_ER_MIN;
  unsigned mask = __ballot_sync(0xffffffff, pass);
  if (mask) {
    int lane = threadIdx.x & 31, leader = __ffs(mask) - 1, base = 0;
    if (lane == leader)
      base = atomicAdd(selected, __popc(mask));
    base = __shfl_sync(0xffffffff, base, leader);
    if (pass)
      active[base + __popc(mask & ((1u << lane) - 1))] = i;
  }
}
#endif
#ifdef NC_COMPACT_TEMPERATURE
__global__ void compactTemperature26(const uint64_t *lows, const int *coords,
                                     int count, const Named *n,
                                     const SeedSpec *l, unsigned char *stages,
                                     const int *active, StageCache26 *next,
                                     int *selected) {
  int j = blockIdx.x * blockDim.x + threadIdx.x;
  if (j >= count)
    return;
  int i = active[j], g = i >> 16;
  uint64_t seed = lows[g] | (uint64_t(i & 65535) << 48);
  StageCache26 cache;
  cache.index = i;
  screenPoint<1>(seed, coords[g * 2], coords[g * 2 + 1], n, l, stages + i, true,
                 &cache);
  bool pass = stages[i] == 2;
  unsigned live = __activemask(), mask = __ballot_sync(live, pass);
  if (mask) {
    int lane = threadIdx.x & 31, leader = __ffs(mask) - 1, base = 0;
    if (lane == leader)
      base = atomicAdd(selected, __popc(mask));
    base = __shfl_sync(live, base, leader);
    if (pass)
      next[base + __popc(mask & ((1u << lane) - 1))] = cache;
  }
}
__global__ void cascadeAfterTemperature26(const uint64_t *lows,
                                          const int *coords, int count,
                                          const Named *n, const SeedSpec *l,
                                          unsigned char *stages,
                                          const StageCache26 *active) {
  int j = blockIdx.x * blockDim.x + threadIdx.x;
  if (j >= count)
    return;
  auto cache = active[j];
  int i = cache.index, g = i >> 16;
  uint64_t seed = lows[g] | (uint64_t(i & 65535) << 48);
  screenPoint<2>(seed, coords[g * 2], coords[g * 2 + 1], n, l, stages + i, true,
                 &cache);
}
#endif
extern "C" uint64_t nc26_create(int device, const uint64_t *hashes,
                                const int *ranges, const uint64_t *oh,
                                const int *banks, const double *fa,
                                int layers) {
  if (device < 0 || device > 7 || layers < 14 || layers > 896)
    return 0;
  if (cudaSetDevice(device) != cudaSuccess)
    return 0;
  auto *h = new Cascade{device, nullptr, nullptr};
  Named ns[NC_NOISE_COUNT];
  for (int i = 0; i < NC_NOISE_COUNT; i++) {
#ifdef NC_COORDINATE_EROSION_BOUNDS
    if (ranges[2 * i + 1] > 64) {
      delete h;
      return 0;
    }
#endif
    if (ranges[2 * i] < 0 || ranges[2 * i + 1] < 1 ||
        ranges[2 * i] + ranges[2 * i + 1] > layers) {
      delete h;
      return 0;
    }
    ns[i] = {hashes[2 * i], hashes[2 * i + 1], ranges[2 * i],
             ranges[2 * i + 1]};
  }
  std::vector<SeedSpec> ls(layers);
  for (int i = 0; i < layers; i++)
    ls[i] = {oh[2 * i], oh[2 * i + 1], banks[i], fa[2 * i],
             float(fa[2 * i + 1])};
#ifdef NC_FIXED_SEED
  h->layerCount = layers;
#endif
  if (cudaMalloc(&h->names, sizeof(ns)) != cudaSuccess ||
      cudaMalloc(&h->layers, layers * sizeof(SeedSpec)) != cudaSuccess ||
      cudaMemcpy(h->names, ns, sizeof(ns), cudaMemcpyHostToDevice) !=
          cudaSuccess ||
      cudaMemcpy(h->layers, ls.data(), layers * sizeof(SeedSpec),
                 cudaMemcpyHostToDevice) != cudaSuccess) {
    cudaFree(h->names);
    cudaFree(h->layers);
    delete h;
    return 0;
  }
  return reinterpret_cast<uint64_t>(h);
}
extern "C" int nc26_noise_count() { return NC_NOISE_COUNT; }
extern "C" int nc26_run(uint64_t raw, uint64_t low, int x, int z,
                        const uint64_t *seeds, int count, unsigned char *out) {
  auto *h = reinterpret_cast<Cascade *>(raw);
  if (!h || count < 1 || count > 65536 || low >= (1ULL << 48))
    return -1;
  auto e = cudaSetDevice(h->device);
  if (e != cudaSuccess)
    return int(e);
  uint64_t *ds = nullptr;
  unsigned char *st = nullptr;
#define TRY(call)                                                              \
  if ((e = (call)) != cudaSuccess)                                             \
  goto done
  TRY(cudaMalloc(&st, count));
  if (seeds) {
    TRY(cudaMalloc(&ds, size_t(count) * 8));
    TRY(cudaMemcpy(ds, seeds, size_t(count) * 8, cudaMemcpyHostToDevice));
  }
  cascade26<<<(count + NC_THREADS - 1) / NC_THREADS, NC_THREADS>>>(
      low, ds, count, x, z, h->names, h->layers, st, nullptr, nullptr, nullptr);
  TRY(cudaGetLastError());
  TRY(cudaMemcpy(out, st, count, cudaMemcpyDeviceToHost));
done:
  cudaFree(ds);
  cudaFree(st);
  return int(e);
#undef TRY
}
// Many warp lanes fail the tight bound after early fast-erosion octaves,
// while their warps still execute all four permutations. Compact the partial
// float sums after octaves two and three before continuing, preserving the
// original octave order and bounds.
#if defined(NC_COMPACT_FAST_ER) && defined(NC_FAST_ER)
#if defined(NC_FAST_ER_PREFIX_OCTAVES) && NC_FAST_ER_PREFIX_OCTAVES == 4 &&    \
    defined(NC_COORDINATE_EROSION_BOUNDS) && defined(NC_INTERVAL_EROSION)
constexpr int kFastErosionCut26 = 2;
struct FastErosionPrefix26 {
  int index;
  float partial;
};
template <int BEGIN, int END>
__device__ bool fastErosionRange26(uint64_t seed, const Named *names,
                                   const SeedSpec *layers, const double *xyz,
                                   float *out) {
  Named name = names[1];
  name.count = NC_FAST_ER_PREFIX_OCTAVES;
  uint64_t s = seed ^ 0x6a09e667f3bcc909ULL;
  XR world = xr2(mix64(s), mix64(s + 0x9e3779b97f4a7c15ULL));
  uint64_t a = next64(world), b = next64(world);
  XR named = xr2(a ^ name.a, b ^ name.b);
  uint64_t banks[4];
  for (int j = 0; j < 4; j++)
    banks[j] = next64(named);
  double suffix[NC_FAST_ER_PREFIX_OCTAVES + 1];
  suffix[name.count] = 0;
  for (int j = name.count - 1; j >= BEGIN; j--)
    suffix[j] =
        suffix[j + 1] + octaveEnvelope26(layers[name.first + j], banks, xyz);
  if (double(out[0]) + suffix[BEGIN] + 1e-5 < NC_FAST_ER_MIN) {
    out[0] = -1e30f;
    return false;
  }
#pragma unroll 1
  for (int j = BEGIN; j < END; j++) {
    if (double(out[0]) + suffix[j] + 1e-5 < NC_FAST_ER_MIN) {
      out[0] = -1e30f;
      return false;
    }
    SeedSpec q = layers[name.first + j];
    XR rng = xr2(banks[2 * q.bank] ^ q.a, banks[2 * q.bank + 1] ^ q.b);
#ifdef NC_SHARED_PERMUTATIONS
    SharedLayer26 p;
    p.perm.bank = permutationBank26();
#else
    Layer p;
#endif
    p.x = double(next64(rng) >> 11) * 0x1p-53 * 256.;
    p.y = double(next64(rng) >> 11) * 0x1p-53 * 256.;
    p.z = double(next64(rng) >> 11) * 0x1p-53 * 256.;
#ifdef NC_SHARED_PERMUTATIONS
    for (int k = 0; k < 64; k++)
      reinterpret_cast<unsigned int *>(
          p.perm.bank)[k * NC_THREADS + threadIdx.x] =
          0x03020100u + unsigned(k) * 0x04040404u;
#else
    for (int k = 0; k < 256; k++)
      p.perm[k] = k;
#endif
#pragma unroll 1
    for (int k = 0; k < 256; k++) {
      int v = k + bound32(rng, 256 - k);
      unsigned char t = p.perm[k];
      p.perm[k] = p.perm[v];
      p.perm[v] = t;
    }
    out[0] +=
        q.amplitude * perlin(p, xyz[0] * q.frequency, xyz[1] * q.frequency,
                             xyz[2] * q.frequency, false);
    double remaining = 0;
    for (int k = j + 1; k < name.count; k++)
      remaining += fabs(double(layers[name.first + k].amplitude));
    if (double(out[0]) + 1.23 * remaining + 1e-5 < NC_FAST_ER_MIN) {
      out[0] = -1e30f;
      return false;
    }
  }
  if constexpr (END < NC_FAST_ER_PREFIX_OCTAVES) {
    if (double(out[0]) + suffix[END] + 1e-5 < NC_FAST_ER_MIN) {
      out[0] = -1e30f;
      return false;
    }
    return true;
  } else
    return out[0] >= NC_FAST_ER_MIN;
}
__global__ void compactErosionPrefix26(const uint64_t *lows, const int *coords,
                                       int count, const Named *n,
                                       const SeedSpec *l,
                                       FastErosionPrefix26 *work,
                                       int *selected) {
  int i = blockIdx.x * blockDim.x + threadIdx.x;
  bool pass = false;
  float value = 0;
  if (i < count) {
    int group = i >> 16;
    uint64_t seed = lows[group] | (uint64_t(i & 65535) << 48);
    double xyz[3] = {(coords[2 * group] + 8) * .25, 0,
                     (coords[2 * group + 1] + 8) * .25};
    pass = fastErosionRange26<0, kFastErosionCut26>(seed, n, l, xyz, &value);
  }
  unsigned mask = __ballot_sync(0xffffffff, pass);
  if (mask) {
    int lane = threadIdx.x & 31, leader = __ffs(mask) - 1, base = 0;
    if (lane == leader)
      base = atomicAdd(selected, __popc(mask));
    base = __shfl_sync(0xffffffff, base, leader);
    if (pass)
      work[base + __popc(mask & ((1u << lane) - 1))] = {i, value};
  }
}
__global__ void compactErosionMiddle26(const uint64_t *lows, const int *coords,
                                       int count, const Named *n,
                                       const SeedSpec *l,
                                       const FastErosionPrefix26 *work,
                                       FastErosionPrefix26 *next,
                                       int *selected) {
  int q = blockIdx.x * blockDim.x + threadIdx.x, index = 0;
  bool pass = false;
  float value = 0;
  if (q < count) {
    auto item = work[q];
    index = item.index;
    value = item.partial;
    int group = index >> 16;
    uint64_t seed = lows[group] | (uint64_t(index & 65535) << 48);
    double xyz[3] = {(coords[2 * group] + 8) * .25, 0,
                     (coords[2 * group + 1] + 8) * .25};
    pass = fastErosionRange26<2, 3>(seed, n, l, xyz, &value);
  }
  unsigned mask = __ballot_sync(0xffffffff, pass);
  if (mask) {
    int lane = threadIdx.x & 31, leader = __ffs(mask) - 1, base = 0;
    if (lane == leader)
      base = atomicAdd(selected, __popc(mask));
    base = __shfl_sync(0xffffffff, base, leader);
    if (pass)
      next[base + __popc(mask & ((1u << lane) - 1))] = {index, value};
  }
}
__global__ void compactErosionSuffix26(const uint64_t *lows, const int *coords,
                                       int count, const Named *n,
                                       const SeedSpec *l,
                                       const FastErosionPrefix26 *work,
                                       int *active, int *selected) {
  int q = blockIdx.x * blockDim.x + threadIdx.x, index = 0;
  bool pass = false;
  if (q < count) {
    auto item = work[q];
    index = item.index;
    float value = item.partial;
    int group = index >> 16;
    uint64_t seed = lows[group] | (uint64_t(index & 65535) << 48);
    double xyz[3] = {(coords[2 * group] + 8) * .25, 0,
                     (coords[2 * group + 1] + 8) * .25};
    pass = fastErosionRange26<3, NC_FAST_ER_PREFIX_OCTAVES>(seed, n, l, xyz,
                                                            &value);
  }
  unsigned mask = __ballot_sync(0xffffffff, pass);
  if (mask) {
    int lane = threadIdx.x & 31, leader = __ffs(mask) - 1, base = 0;
    if (lane == leader)
      base = atomicAdd(selected, __popc(mask));
    base = __shfl_sync(0xffffffff, base, leader);
    if (pass)
      active[base + __popc(mask & ((1u << lane) - 1))] = index;
  }
}
static cudaError_t launchErosion26(const uint64_t *lows, const int *coords,
                                   int count, const Named *n, const SeedSpec *l,
                                   int *active, int *selected,
                                   CascadeScratch26 *scratch = nullptr) {
  FastErosionPrefix26 *work = nullptr;
  FastErosionPrefix26 *middle = nullptr;
  int *selectedPrefix = nullptr;
  int prefixCount = 0;
  int middleCount = 0;
  cudaError_t error;
#define SPLIT_TRY(call)                                                        \
  if ((error = (call)) != cudaSuccess)                                         \
  goto split_done
  SPLIT_TRY(allocateCascade26(scratch, &work,
                              size_t(count) * sizeof(FastErosionPrefix26)));
  SPLIT_TRY(allocateCascade26(scratch, &selectedPrefix, sizeof(int)));
  SPLIT_TRY(cudaMemset(selectedPrefix, 0, sizeof(int)));
  compactErosionPrefix26<<<(count + NC_THREADS - 1) / NC_THREADS, NC_THREADS>>>(
      lows, coords, count, n, l, work, selectedPrefix);
  SPLIT_TRY(cudaGetLastError());
  SPLIT_TRY(cudaMemcpy(&prefixCount, selectedPrefix, sizeof(int),
                       cudaMemcpyDeviceToHost));
  if (prefixCount) {
    SPLIT_TRY(allocateCascade26(
        scratch, &middle, size_t(prefixCount) * sizeof(FastErosionPrefix26)));
    SPLIT_TRY(cudaMemset(selectedPrefix, 0, sizeof(int)));
    compactErosionMiddle26<<<(prefixCount + NC_THREADS - 1) / NC_THREADS,
                             NC_THREADS>>>(lows, coords, prefixCount, n, l,
                                           work, middle, selectedPrefix);
    SPLIT_TRY(cudaGetLastError());
    SPLIT_TRY(cudaMemcpy(&middleCount, selectedPrefix, sizeof(int),
                         cudaMemcpyDeviceToHost));
    if (middleCount)
      compactErosionSuffix26<<<(middleCount + NC_THREADS - 1) / NC_THREADS,
                               NC_THREADS>>>(lows, coords, middleCount, n, l,
                                             middle, active, selected);
    SPLIT_TRY(cudaGetLastError());
  }
split_done:
  auto cleanup = releaseCascade26(scratch, work);
  if (error == cudaSuccess)
    error = cleanup;
  cleanup = releaseCascade26(scratch, middle);
  if (error == cudaSuccess)
    error = cleanup;
  cleanup = releaseCascade26(scratch, selectedPrefix);
  if (error == cudaSuccess)
    error = cleanup;
  return error;
#undef SPLIT_TRY
}

#else
static cudaError_t launchErosion26(const uint64_t *lows, const int *coords,
                                   int count, const Named *n, const SeedSpec *l,
                                   int *active, int *selected,
                                   CascadeScratch26 *scratch = nullptr) {
  compactErosion<<<(count + NC_THREADS - 1) / NC_THREADS, NC_THREADS>>>(
      lows, coords, count, n, l, active, selected);
  return cudaGetLastError();
}
#endif
#endif

extern "C" int nc26_batch(uint64_t raw, const uint64_t *lows, const int *coords,
                          int roots, unsigned char *out) {
  auto *h = reinterpret_cast<Cascade *>(raw);
  if (!h || roots < 1 || roots > 256)
    return -1;
  auto e = cudaSetDevice(h->device);
  if (e != cudaSuccess)
    return int(e);
  uint64_t *dl = nullptr;
  int *dc = nullptr;
  unsigned char *st = nullptr;
  int count = roots * 65536;
  int *active = nullptr;
  int *selected = nullptr;
#if defined(NC_COMPACT_FAST_ER) && defined(NC_FAST_ER)
  int selectedCount = 0;
#ifdef NC_COMPACT_TEMPERATURE
  int selectedCount2 = 0;
  StageCache26 *active2 = nullptr;
  int *selected2 = nullptr;
#endif
#endif
#define TRY(call)                                                              \
  if ((e = (call)) != cudaSuccess)                                             \
  goto done
  TRY(cudaMalloc(&dl, roots * sizeof(uint64_t)));
  TRY(cudaMalloc(&dc, roots * 2 * sizeof(int)));
  TRY(cudaMalloc(&st, count));
  TRY(cudaMemcpy(dl, lows, roots * sizeof(uint64_t), cudaMemcpyHostToDevice));
  TRY(cudaMemcpy(dc, coords, roots * 2 * sizeof(int), cudaMemcpyHostToDevice));
#if defined(NC_COMPACT_FAST_ER) && defined(NC_FAST_ER)
  TRY(cudaMalloc(&active, count * sizeof(int)));
  TRY(cudaMalloc(&selected, sizeof(int)));
  TRY(cudaMemset(selected, 0, sizeof(int)));
  TRY(cudaMemset(st, 0, count));
  TRY(launchErosion26(dl, dc, count, h->names, h->layers, active, selected));
  TRY(cudaMemcpy(&selectedCount, selected, sizeof(int),
                 cudaMemcpyDeviceToHost));
#ifdef NC_COMPACT_TEMPERATURE
  if (selectedCount) {
    TRY(cudaMalloc(&active2, selectedCount * sizeof(StageCache26)));
    TRY(cudaMalloc(&selected2, sizeof(int)));
    TRY(cudaMemset(selected2, 0, sizeof(int)));
    compactTemperature26<<<(selectedCount + NC_THREADS - 1) / NC_THREADS,
                           NC_THREADS>>>(dl, dc, selectedCount, h->names,
                                         h->layers, st, active, active2,
                                         selected2);
    TRY(cudaGetLastError());
    TRY(cudaMemcpy(&selectedCount2, selected2, sizeof(int),
                   cudaMemcpyDeviceToHost));
    if (selectedCount2)
      cascadeAfterTemperature26<<<
          (selectedCount2 + NC_THREADS - 1) / NC_THREADS, NC_THREADS>>>(
          dl, dc, selectedCount2, h->names, h->layers, st, active2);
  }
#else
  if (selectedCount)
    cascade26<<<(selectedCount + NC_THREADS - 1) / NC_THREADS, NC_THREADS>>>(
        0, nullptr, selectedCount, 0, 0, h->names, h->layers, st, dl, dc,
        active);
#endif
#else
  cascade26<<<(count + NC_THREADS - 1) / NC_THREADS, NC_THREADS>>>(
      0, nullptr, count, 0, 0, h->names, h->layers, st, dl, dc, nullptr);
#endif
  TRY(cudaGetLastError());
  TRY(cudaMemcpy(out, st, count, cudaMemcpyDeviceToHost));
done:
#ifdef NC_COMPACT_TEMPERATURE
  cudaFree(active2);
  cudaFree(selected2);
#endif
  cudaFree(dl);
  cudaFree(dc);
  cudaFree(st);
  cudaFree(active);
  cudaFree(selected);
  return int(e);
#undef TRY
}
extern "C" void nc26_destroy(uint64_t raw) {
  auto *h = reinterpret_cast<Cascade *>(raw);
  if (!h)
    return;
  cudaSetDevice(h->device);
  cudaFree(h->names);
  cudaFree(h->layers);
#ifdef NC_FIXED_SEED
  cudaFree(h->cache);
  cudaFree(h->positions);
  cudaFree(h->batchNames);
  cudaFree(h->batchCache);
  cudaFree(h->batchOutput);
#endif
  delete h;
}
extern "C" void nc26_histogram(const unsigned char *stages, int roots, int bins,
                               int *output) {
  for (int root = 0; root < roots; root++) {
    auto *counts = output + root * bins;
    std::memset(counts, 0, bins * sizeof(int));
    auto *input = stages + root * 65536;
    for (int offset = 0; offset < 65536; offset += 8) {
      uint64_t word;
      std::memcpy(&word, input + offset, sizeof(word));
      if (word)
        for (int k = 0; k < 8; k++)
          if (input[offset + k])
            counts[input[offset + k]]++;
    }
    counts[0] = 65536;
    for (int i = 1; i < bins; i++)
      counts[0] -= counts[i];
  }
}

// Same cascade predicates; transfer per-root stage counters and sparse
// survivors instead of the complete byte status volume. The raw APIs above are
// retained.
__global__ void summarizeCascade26(const unsigned char *stages, int finalStage,
                                   int *histogram, uint32_t *survivors,
                                   int capacity, int *survivorCount) {
  const int root = blockIdx.x, bins = finalStage + 1;
  __shared__ int counts[32];
  if (threadIdx.x < bins)
    counts[threadIdx.x] = 0;
  __syncthreads();
  const int lane = threadIdx.x & 31;
  for (int high16 = threadIdx.x; high16 < 65536; high16 += blockDim.x) {
    const int stage = stages[root * 65536 + high16];
    unsigned peers = __match_any_sync(0xffffffff, stage);
    if (lane == __ffs(peers) - 1)
      atomicAdd(counts + stage, __popc(peers));
    const bool selected = stage == finalStage;
    const unsigned mask = __ballot_sync(0xffffffff, selected);
    if (mask) {
      const int leader = __ffs(mask) - 1;
      int base = 0;
      if (lane == leader)
        base = atomicAdd(survivorCount, __popc(mask));
      base = __shfl_sync(0xffffffff, base, leader);
      const int slot = base + __popc(mask & ((1u << lane) - 1));
      if (selected && slot < capacity)
        survivors[slot] = uint32_t(root) * 65536u + uint32_t(high16);
    }
  }
  __syncthreads();
  if (threadIdx.x < bins)
    histogram[root * bins + threadIdx.x] = counts[threadIdx.x];
}

extern "C" int nc26_batch_compact(uint64_t raw, const uint64_t *lows,
                                  const int *coords, int roots, int finalStage,
                                  int *histogram, uint32_t *survivors,
                                  int capacity, int *survivorCount) {
  auto *h = reinterpret_cast<Cascade *>(raw);
  CascadeScratch26 *scratch = nullptr;
#ifdef NC_REUSE_WORKSPACE
  if (h) {
    scratch = &h->scratch;
    scratch->reset();
  }
#endif

  constexpr int expectedFinalStage = 20
#ifdef NC_SURFACE_GATE
                                     + 1
#endif
#ifdef NC_DEEP_CHEESE
                                     + 2
#endif
      ;
  if (finalStage != expectedFinalStage)
    return -1;
  if (!h || roots < 1 || roots > 2048 || finalStage < 1 || finalStage > 31 ||
      capacity < 0 || !lows || !coords || !histogram || !survivorCount ||
      (capacity && !survivors))
    return -1;
  *survivorCount = 0;
  auto error = cudaSetDevice(h->device);
  if (error != cudaSuccess)
    return int(error);
  uint64_t *dl = nullptr;
  int *dc = nullptr;
  unsigned char *stages = nullptr;
  int *dh = nullptr;
  uint32_t *indices = nullptr;
  int *count = nullptr;
  int *active = nullptr;
  int *selected = nullptr;
#if defined(NC_COMPACT_FAST_ER) && defined(NC_FAST_ER)
  int selectedCount = 0;
#ifdef NC_COMPACT_TEMPERATURE
  int selectedCount2 = 0;
  StageCache26 *active2 = nullptr;
  int *selected2 = nullptr;
#endif
#endif
  int status = 0;
  const int trials = roots * 65536, bins = finalStage + 1;
#define COMPACT_TRY(call)                                                      \
  if ((error = (call)) != cudaSuccess) {                                       \
    status = int(error);                                                       \
    goto compact_done;                                                         \
  }
  COMPACT_TRY(
      allocateCascade26(scratch, &dl, size_t(roots) * sizeof(uint64_t)));
  COMPACT_TRY(allocateCascade26(scratch, &dc, size_t(roots) * 2 * sizeof(int)));
  COMPACT_TRY(allocateCascade26(scratch, &stages, size_t(trials)));
  COMPACT_TRY(
      allocateCascade26(scratch, &dh, size_t(roots) * bins * sizeof(int)));
  if (capacity)
    COMPACT_TRY(allocateCascade26(scratch, &indices,
                                  size_t(capacity) * sizeof(uint32_t)));
  COMPACT_TRY(allocateCascade26(scratch, &count, sizeof(int)));
  COMPACT_TRY(cudaMemset(count, 0, sizeof(int)));
  COMPACT_TRY(cudaMemcpy(dl, lows, size_t(roots) * sizeof(uint64_t),
                         cudaMemcpyHostToDevice));
  COMPACT_TRY(cudaMemcpy(dc, coords, size_t(roots) * 2 * sizeof(int),
                         cudaMemcpyHostToDevice));
  // Preserve the original optional erosion/temperature compaction pipeline.
#if defined(NC_COMPACT_FAST_ER) && defined(NC_FAST_ER)
  COMPACT_TRY(allocateCascade26(scratch, &active, trials * sizeof(int)));
  COMPACT_TRY(allocateCascade26(scratch, &selected, sizeof(int)));
  COMPACT_TRY(cudaMemset(selected, 0, sizeof(int)));
  COMPACT_TRY(cudaMemset(stages, 0, trials));
  COMPACT_TRY(launchErosion26(dl, dc, trials, h->names, h->layers, active,
                              selected, scratch));
  COMPACT_TRY(cudaMemcpy(&selectedCount, selected, sizeof(int),
                         cudaMemcpyDeviceToHost));
#ifdef NC_COMPACT_TEMPERATURE
  if (selectedCount) {
    COMPACT_TRY(allocateCascade26(scratch, &active2,
                                  selectedCount * sizeof(StageCache26)));
    COMPACT_TRY(allocateCascade26(scratch, &selected2, sizeof(int)));
    COMPACT_TRY(cudaMemset(selected2, 0, sizeof(int)));
    compactTemperature26<<<(selectedCount + NC_THREADS - 1) / NC_THREADS,
                           NC_THREADS>>>(dl, dc, selectedCount, h->names,
                                         h->layers, stages, active, active2,
                                         selected2);
    COMPACT_TRY(cudaGetLastError());
    COMPACT_TRY(cudaMemcpy(&selectedCount2, selected2, sizeof(int),
                           cudaMemcpyDeviceToHost));
    if (selectedCount2)
      cascadeAfterTemperature26<<<
          (selectedCount2 + NC_THREADS - 1) / NC_THREADS, NC_THREADS>>>(
          dl, dc, selectedCount2, h->names, h->layers, stages, active2);
  }
#else
  if (selectedCount)
    cascade26<<<(selectedCount + NC_THREADS - 1) / NC_THREADS, NC_THREADS>>>(
        0, nullptr, selectedCount, 0, 0, h->names, h->layers, stages, dl, dc,
        active);
#endif
#else
  cascade26<<<(trials + NC_THREADS - 1) / NC_THREADS, NC_THREADS>>>(
      0, nullptr, trials, 0, 0, h->names, h->layers, stages, dl, dc, nullptr);
#endif
  COMPACT_TRY(cudaGetLastError());
  summarizeCascade26<<<roots, 256>>>(stages, finalStage, dh, indices, capacity,
                                     count);
  COMPACT_TRY(cudaGetLastError());
  COMPACT_TRY(cudaMemcpy(histogram, dh, size_t(roots) * bins * sizeof(int),
                         cudaMemcpyDeviceToHost));
  COMPACT_TRY(
      cudaMemcpy(survivorCount, count, sizeof(int), cudaMemcpyDeviceToHost));
  // Count/counters remain available on capacity overflow; partial indices are
  // deliberately not returned. The caller can retry with the required capacity.
  if (*survivorCount > capacity) {
    status = -2;
    goto compact_done;
  }
  if (*survivorCount)
    COMPACT_TRY(cudaMemcpy(survivors, indices,
                           size_t(*survivorCount) * sizeof(uint32_t),
                           cudaMemcpyDeviceToHost));
compact_done:
#if defined(NC_COMPACT_FAST_ER) && defined(NC_FAST_ER) &&                      \
    defined(NC_COMPACT_TEMPERATURE)
  releaseCascade26(scratch, active2);
  releaseCascade26(scratch, selected2);
#endif
  releaseCascade26(scratch, active);
  releaseCascade26(scratch, selected);
  releaseCascade26(scratch, dl);
  releaseCascade26(scratch, dc);
  releaseCascade26(scratch, stages);
  releaseCascade26(scratch, dh);
  releaseCascade26(scratch, indices);
  releaseCascade26(scratch, count);
  return status;
#undef COMPACT_TRY
}
