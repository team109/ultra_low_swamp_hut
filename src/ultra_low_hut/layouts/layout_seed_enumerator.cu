#include <cuda_runtime.h>
#include <stdint.h>
static constexpr uint64_t MASK = (1ULL << 48) - 1, A = 0x5deece66dULL,
                          AI = 0xdfe05bcb1365ULL;
static constexpr uint64_t DOMAIN = 1125902188544ULL, PERM = 8388593ULL,
                          ROTATION = 19606000123ULL;
__device__ uint32_t bits(uint64_t &s, int n) {
  s = (s * A + 11) & MASK;
  return s >> (48 - n);
}
__device__ int integer(uint64_t &s, int n) {
  if ((n & (n - 1)) == 0)
    return (uint64_t(n) * bits(s, 31)) >> 31;
  uint32_t b, v;
  do {
    b = bits(s, 31);
    v = b % n;
  } while (uint64_t(b - v) + n - 1 >= 0x80000000ULL);
  return v;
}
__global__ void scan(uint64_t begin, uint32_t count, int mode, uint64_t *out,
                     uint32_t *found) {
  uint32_t index = blockIdx.x * blockDim.x + threadIdx.x;
  if (index >= count)
    return;
  uint64_t firstState = ((begin + index) * PERM + ROTATION) % DOMAIN,
           state = firstState;
  uint64_t first = state >> 22, second = bits(state, 27);
  if (double((first << 27) + second) * 0x1p-53 >= double(.004f))
    return;
  uint64_t target = (((firstState - 11) * AI) & MASK) ^ A;
  unsigned active = __activemask(), mask = __ballot_sync(active, true);
  int lane = threadIdx.x & 31, leader = __ffs(mask) - 1;
  uint32_t base = 0;
  if (lane == leader)
    base = atomicAdd(found, __popc(mask));
  base = __shfl_sync(active, base, leader);
  if (base + __popc(mask & ((1u << lane) - 1)) < (1u << 24))
    out[base + __popc(mask & ((1u << lane) - 1))] = target;
}
struct Scanner {
  int device;
  uint32_t capacity;
  uint64_t *out;
  uint32_t *count;
};
extern "C" int scan_open(int device, uint32_t capacity, void **handle) {
  auto e = cudaSetDevice(device);
  if (e != cudaSuccess)
    return e;
  auto *s = new Scanner{device, capacity, nullptr, nullptr};
  e = cudaMalloc(&s->out, uint64_t(capacity) * 8);
  if (e == cudaSuccess)
    e = cudaMalloc(&s->count, 4);
  if (e != cudaSuccess) {
    cudaFree(s->out);
    cudaFree(s->count);
    delete s;
    return e;
  }
  *handle = s;
  return 0;
}
extern "C" int scan_step(void *handle, uint64_t begin, uint32_t count, int mode,
                         uint64_t *out, uint32_t *found) {
  auto *s = (Scanner *)handle;
  if (!s || begin + count > DOMAIN)
    return -1;
  auto e = cudaSetDevice(s->device);
  if (e != cudaSuccess)
    return e;
  if ((e = cudaMemset(s->count, 0, 4)) != cudaSuccess)
    return e;
  scan<<<(count + 255) / 256, 256>>>(begin, count, mode, s->out, s->count);
  if ((e = cudaGetLastError()) != cudaSuccess)
    return e;
  if ((e = cudaMemcpy(found, s->count, 4, cudaMemcpyDeviceToHost)) !=
      cudaSuccess)
    return e;
  if (*found > s->capacity)
    return -2;
  return cudaMemcpy(out, s->out, uint64_t(*found) * 8, cudaMemcpyDeviceToHost);
}
extern "C" void scan_close(void *handle) {
  auto *s = (Scanner *)handle;
  if (!s)
    return;
  cudaSetDevice(s->device);
  cudaFree(s->out);
  cudaFree(s->count);
  delete s;
}
