// Full world-seed -> named octave permutations -> scalar float noise, on GPU.
// Shares the independently validated 26.3 Perlin evaluation implementation.
#include "perlin_noise.cuh"
struct XR {
  uint64_t a, b;
};
__device__ uint64_t rotl64(uint64_t v, int n) {
  return (v << n) | (v >> (64 - n));
}
__device__ uint64_t mix64(uint64_t v) {
  v = (v ^ (v >> 30)) * 0xbf58476d1ce4e5b9ULL;
  v = (v ^ (v >> 27)) * 0x94d049bb133111ebULL;
  return v ^ (v >> 31);
}
__device__ XR xr2(uint64_t a, uint64_t b) {
  if (!(a | b)) {
    a = 0x9e3779b97f4a7c15ULL;
    b = 0x6a09e667f3bcc909ULL;
  }
  return {a, b};
}
__device__ uint64_t next64(XR &r) {
  uint64_t a = r.a, b = r.b, result = rotl64(a + b, 17) + a;
  b ^= a;
  r.a = rotl64(a, 49) ^ b ^ (b << 21);
  r.b = rotl64(b, 28);
  return result;
}
__device__ uint32_t bound32(XR &r, uint32_t bound) {
  uint64_t m = uint64_t(uint32_t(next64(r))) * bound;
  uint32_t low = m;
  if (low < bound) {
    uint32_t threshold = uint32_t(-bound) % bound;
    while (low < threshold) {
      m = uint64_t(uint32_t(next64(r))) * bound;
      low = m;
    }
  }
  return uint32_t(m >> 32);
}
struct SeedSpec {
  uint64_t a, b;
  int bank;
  double frequency;
  float amplitude;
};
__global__ void seeded(const uint64_t *seeds, const double *xyz, int n,
                       uint64_t name0, uint64_t name1, const SeedSpec *spec,
                       int layers, float *out) {
  int i = blockIdx.x * blockDim.x + threadIdx.x;
  if (i >= n)
    return;
  uint64_t s = seeds[i] ^ 0x6a09e667f3bcc909ULL;
  XR world = xr2(mix64(s), mix64(s + 0x9e3779b97f4a7c15ULL));
  uint64_t a = next64(world), b = next64(world);
  XR named = xr2(a ^ name0, b ^ name1);
  uint64_t banks[4];
  for (int j = 0; j < 4; j++)
    banks[j] = next64(named);
  float sum = 0;
  for (int j = 0; j < layers; j++) {
    SeedSpec q = spec[j];
    XR rng = xr2(banks[2 * q.bank] ^ q.a, banks[2 * q.bank + 1] ^ q.b);
    Layer p;
    p.x = double(next64(rng) >> 11) * 0x1p-53 * 256.;
    p.y = double(next64(rng) >> 11) * 0x1p-53 * 256.;
    p.z = double(next64(rng) >> 11) * 0x1p-53 * 256.;
    for (int k = 0; k < 256; k++)
      p.perm[k] = k;
    for (int k = 0; k < 256; k++) {
      int v = k + bound32(rng, 256 - k);
      unsigned char tmp = p.perm[k];
      p.perm[k] = p.perm[v];
      p.perm[v] = tmp;
    }
    sum += q.amplitude * perlin(p, xyz[3 * i] * q.frequency,
                                xyz[3 * i + 1] * q.frequency,
                                xyz[3 * i + 2] * q.frequency, false);
  }
  out[i] = sum;
}
extern "C" int nv26_seed_samples(int device, const uint64_t *seeds,
                                 const double *xyz, int n, const uint64_t *name,
                                 const uint64_t *octaves, const int *banks,
                                 const double *fa, int layers, float *out) {
  if (device < 4 || device > 7 || n < 1 || layers < 1 || layers > 64)
    return -1;
  auto e = cudaSetDevice(device);
  if (e != cudaSuccess)
    return int(e);
  std::vector<SeedSpec> spec(layers);
  for (int j = 0; j < layers; j++)
    spec[j] = {octaves[2 * j], octaves[2 * j + 1], banks[j], fa[2 * j],
               float(fa[2 * j + 1])};
  uint64_t *ds = nullptr;
  double *dx = nullptr;
  SeedSpec *dq = nullptr;
  float *dy = nullptr;
// Every allocation is released, including failure paths.
#define TRY(call)                                                              \
  if ((e = (call)) != cudaSuccess)                                             \
  goto done
  TRY(cudaMalloc(&ds, size_t(n) * sizeof(uint64_t)));
  TRY(cudaMalloc(&dx, size_t(n) * 3 * sizeof(double)));
  TRY(cudaMalloc(&dq, layers * sizeof(SeedSpec)));
  TRY(cudaMalloc(&dy, size_t(n) * sizeof(float)));
  TRY(cudaMemcpy(ds, seeds, size_t(n) * sizeof(uint64_t),
                 cudaMemcpyHostToDevice));
  TRY(cudaMemcpy(dx, xyz, size_t(n) * 3 * sizeof(double),
                 cudaMemcpyHostToDevice));
  TRY(cudaMemcpy(dq, spec.data(), layers * sizeof(SeedSpec),
                 cudaMemcpyHostToDevice));
  seeded<<<(n + 127) / 128, 128>>>(ds, dx, n, name[0], name[1], dq, layers, dy);
  TRY(cudaGetLastError());
  TRY(cudaMemcpy(out, dy, size_t(n) * sizeof(float), cudaMemcpyDeviceToHost));
done:
  cudaFree(ds);
  cudaFree(dx);
  cudaFree(dq);
  cudaFree(dy);
  return int(e);
#undef TRY
}
