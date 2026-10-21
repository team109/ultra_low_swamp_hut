#pragma once
#include "surface_splines26.cuh"
template <int depth> __device__ float surfaceSpline26(int id, const float *p) {
  SurfaceNode26 n = surfaceNodes26[id];
  if (n.coord < 0)
    return n.constant;
  if constexpr (depth == 0) {
    return nanf("");
  } else {
    float value = p[n.coord];
    int i = 0;
    while (i < n.count && value >= surfacePoints26[n.start + i].location)
      i++;
    i--;
    if (i < 0) {
      auto q = surfacePoints26[n.start];
      return surfaceSpline26<depth - 1>(q.child, p) +
             q.derivative * (value - q.location);
    }
    if (i == n.count - 1) {
      auto q = surfacePoints26[n.start + i];
      return surfaceSpline26<depth - 1>(q.child, p) +
             q.derivative * (value - q.location);
    }
    auto a = surfacePoints26[n.start + i], b = surfacePoints26[n.start + i + 1];
    float t = (value - a.location) / (b.location - a.location);
    float av = surfaceSpline26<depth - 1>(a.child, p),
          bv = surfaceSpline26<depth - 1>(b.child, p);
    float l = a.derivative * (b.location - a.location) - (bv - av),
          r = -b.derivative * (b.location - a.location) + (bv - av);
    return mixf(t, av, bv) + t * (1.f - t) * mixf(t, l, r);
  }
}
__device__ void surfaceFactors26(float c, float e, float w, float *out) {
  float p[4] = {c, e, -(fabsf(fabsf(w) - .6666667f) - .33333334f) * 3.f, w};
  out[0] = surfaceSpline26<6>(SURFACE_OFFSET26, p);
  out[1] = surfaceSpline26<6>(SURFACE_FACTOR26, p);
}
// Root of the ordinary-height preliminary density branch, quantized to 8.
// Used only as a coarse diagnostic; not an exact aquifer or surface function.
__device__ float surfaceApprox26(float offset, float factor) {
  return float(
      floor(fmin(320.,
                 fmax(-40., 128. + 128. * (double(offset) - double(.50375f)) -
                                35. / factor)) /
            8.) *
      8.);
}
