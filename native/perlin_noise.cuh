#pragma once
// Float Perlin evaluation shared by the GPU noise cascade.
#include <cmath>
#include <cstdint>
#include <cuda_runtime.h>
#include <vector>
struct Layer {
  double frequency, x, y, z;
  float amplitude;
  unsigned char perm[256];
};
struct Handle {
  int device, n;
  Layer *layers;
  float *buffer = nullptr;
  size_t capacity = 0;
  cudaStream_t stream;
};
__device__ __constant__ int gradients[16][3] = {
    {1, 1, 0},  {-1, 1, 0},  {1, -1, 0}, {-1, -1, 0}, {1, 0, 1},  {-1, 0, 1},
    {1, 0, -1}, {-1, 0, -1}, {0, 1, 1},  {0, -1, 1},  {0, 1, -1}, {0, -1, -1},
    {1, 1, 0},  {0, -1, 1},  {-1, 1, 0}, {0, -1, -1}};
__device__ float mixf(float t, float a, float b) { return a + t * (b - a); }
__device__ float smoothf(float t) {
  return t * t * t * (t * (t * 6.f - 15.f) + 10.f);
}
__device__ double wrap(double x) {
  return x - floor(x / 33554432. + .5) * 33554432.;
}
template <typename NoiseLayer>
__device__ float perlin(const NoiseLayer &p, double xx, double yy, double zz,
                        bool volume) {
  double x = wrap(xx) + p.x, y = wrap(yy) + p.y, z = wrap(zz) + p.z;
  int ix = int(floor(x)), iy = int(floor(y)), iz = int(floor(z));
  float fx = float(x - ix), fy = float(y - iy), fz = float(z - iz), v[8];
  for (int dz = 0; dz < 2; ++dz)
    for (int dy = 0; dy < 2; ++dy)
      for (int dx = 0; dx < 2; ++dx) {
        int h = p.perm[(p.perm[(p.perm[(ix + dx) & 255] + iy + dy) & 255] + iz +
                        dz) &
                       255] &
                15;
        float a = gradients[h][0] * (fx - dx), b = gradients[h][1] * (fy - dy),
              c = gradients[h][2] * (fz - dz);
        v[dz * 4 + dy * 2 + dx] = volume ? (a + c) + b : (a + b) + c;
      }
  float a = smoothf(fx), b = smoothf(fy), c = smoothf(fz);
  return mixf(c, mixf(b, mixf(a, v[0], v[1]), mixf(a, v[2], v[3])),
              mixf(b, mixf(a, v[4], v[5]), mixf(a, v[6], v[7])));
}
