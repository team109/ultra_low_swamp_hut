#ifndef HUT_SALT
#define HUT_SALT 14357620ULL
#endif
#ifndef HUT_SPACING
#define HUT_SPACING 32
#endif
#ifndef HUT_SEPARATION
#define HUT_SEPARATION 8
#endif
#pragma once
#include <stdint.h>
#ifdef __CUDACC__
#define MHD __host__ __device__
#else
#define MHD
#endif
namespace mine26 {
#ifndef MINE26_CAP
#define MINE26_CAP 512
#endif
constexpr int CAP = MINE26_CAP, ENTRY_CAP = 64;
enum { NORTH = 0, EAST = 1, SOUTH = 2, WEST = 3 };
struct Box {
  int x0, y0, z0, x1, y1, z1;
  MHD void move(int x, int y, int z) {
    x0 += x;
    x1 += x;
    y0 += y;
    y1 += y;
    z0 += z;
    z1 += z;
  }
};
#ifdef MINE26_PACKED_COLLISION
// Zero means fallback: either an out-of-range box or the valid all-minus128
// encoding. No stored/candidate box is ever treated as compressed in that case.
MHD inline uint32_t collisionBoxKey(const Box &b) {
  if (b.x0 < -128 || b.x0 > 127 || b.x1 < -128 || b.x1 > 127 || b.z0 < -128 ||
      b.z0 > 127 || b.z1 < -128 || b.z1 > 127)
    return 0;
  return uint32_t(b.x0 + 128) | (uint32_t(b.x1 + 128) << 8) |
         (uint32_t(b.z0 + 128) << 16) | (uint32_t(b.z1 + 128) << 24);
}
#endif
struct Piece {
  Box b;
  int type, dir, depth, flags;
}; // room=0,corridor=1,cross=2,stairs=3
struct LCG {
  uint64_t s;
  MHD void seed(uint64_t x) { s = (x ^ 0x5deece66dULL) & ((1ULL << 48) - 1); }
  MHD uint32_t bits(int n) {
    s = (s * 0x5deece66dULL + 11) & ((1ULL << 48) - 1);
    return uint32_t(s >> (48 - n));
  }
  MHD int integer(int bound) {
    if ((bound & (bound - 1)) == 0)
      return int((uint64_t(bound) * bits(31)) >> 31);
    uint32_t b, v;
    do {
      b = bits(31);
      v = b % bound;
    } while (uint64_t(b - v) + bound - 1 >= 0x80000000ULL);
    return v;
  }
  MHD uint64_t longValue() {
    uint64_t hi = uint64_t(int64_t(int32_t(bits(32))));
    uint64_t lo = uint64_t(int64_t(int32_t(bits(32))));
    return (hi << 32) + lo;
  }
  MHD void large(uint64_t world, int x, int z) {
    seed(world);
    uint64_t a = longValue(), b = longValue();
    seed(uint64_t(int64_t(x)) * a ^ uint64_t(int64_t(z)) * b ^ world);
  }
  MHD double real() {
    uint64_t a = bits(26), b = bits(27);
    return double((a << 27) + b) * 0x1p-53;
  }
};
#ifdef MINE26_STRIDED
template <class T> struct LaneArray {
  T *base;
  MHD T &operator[](int i) { return base[i * 32]; }
  MHD const T &operator[](int i) const { return base[i * 32]; }
};
#endif
struct Layout {
#ifdef MINE26_STRIDED
  LaneArray<Piece> p;
  LaneArray<Box> entries;
  MHD void bind(Piece *pieces, Box *boxes, int i) {
    p.base = pieces + (i / 32) * CAP * 32 + i % 32;
    entries.base = boxes + (i / 32) * ENTRY_CAP * 32 + i % 32;
  }
#else
  Piece p[CAP];
  Box entries[ENTRY_CAP];
#endif
#ifdef MINE26_PACKED_COLLISION
  uint32_t collisionKeys[CAP];
#endif
  int n = 0, ne = 0;
  bool overflow = false, roomPruned = false;
  LCG rng;
#ifdef MINE26_PACKED_COLLISION
  MHD bool collides(const Box &b) const {
    if (!collisionBoxKey(b)) {
      for (int i = 0; i < n; i++) {
        const Box &a = p[i].b;
        if (a.x0 <= b.x1 && a.x1 >= b.x0 && a.y0 <= b.y1 && a.y1 >= b.y0 &&
            a.z0 <= b.z1 && a.z1 >= b.z0)
          return true;
      }
      return false;
    }
    const int x0 = b.x0 + 128, x1 = b.x1 + 128, z0 = b.z0 + 128,
              z1 = b.z1 + 128;
    for (int i = 0; i < n; i++) {
      uint32_t key = collisionKeys[i];
      if (!key) {
        const Box &a = p[i].b;
        if (a.x0 <= b.x1 && a.x1 >= b.x0 && a.y0 <= b.y1 && a.y1 >= b.y0 &&
            a.z0 <= b.z1 && a.z1 >= b.z0)
          return true;
        continue;
      }
      if (int(key & 255) > x1 || int((key >> 8) & 255) < x0 ||
          int((key >> 16) & 255) > z1 || int(key >> 24) < z0)
        continue;
      const Box &a = p[i].b;
      if (a.y0 <= b.y1 && a.y1 >= b.y0)
        return true;
    }
    return false;
  }
#else
  MHD bool collides(const Box &b) const {
    for (int i = 0; i < n; i++) {
      const Box &a = p[i].b;
      if (a.x0 <= b.x1 && a.x1 >= b.x0 && a.y0 <= b.y1 && a.y1 >= b.y0 &&
          a.z0 <= b.z1 && a.z1 >= b.z0)
        return true;
    }
    return false;
  }
#endif
  MHD int add(Piece q) {
#ifdef HUNT_ROOM_MAX_Y
    if (q.b.y0 < -12 - HUNT_ROOM_MAX_Y) {
      overflow = true;
      roomPruned = true;
      return -1;
    }
#endif
    if (n == CAP) {
      overflow = true;
      return -1;
    }
    p[n] = q;
#ifdef MINE26_PACKED_COLLISION
    collisionKeys[n] = collisionBoxKey(q.b);
#endif
    return n++;
  }
  MHD int child(int x, int y, int z, int dir, int depth) {
    if (overflow || depth > 8 || x - p[0].b.x0 > 80 || x - p[0].b.x0 < -80 ||
        z - p[0].b.z0 > 80 || z - p[0].b.z0 < -80)
      return -1;
    int choice = rng.integer(100), type, flags = 0;
    Box b;
    if (choice >= 80) {
      type = 2;
      int top = rng.integer(4) == 0 ? 6 : 2;
      flags = top > 2;
      if (dir == NORTH)
        b = {-1, 0, -4, 3, top, 0};
      else if (dir == SOUTH)
        b = {-1, 0, 0, 3, top, 4};
      else if (dir == WEST)
        b = {-4, 0, -1, 0, top, 3};
      else
        b = {0, 0, -1, 4, top, 3};
      b.move(x, y, z);
      if (collides(b))
        return -1;
    } else if (choice >= 70) {
      type = 3;
      if (dir == NORTH)
        b = {0, -5, -8, 2, 2, 0};
      else if (dir == SOUTH)
        b = {0, -5, 0, 2, 2, 8};
      else if (dir == WEST)
        b = {-8, -5, 0, 0, 2, 2};
      else
        b = {0, -5, 0, 8, 2, 2};
      b.move(x, y, z);
      if (collides(b))
        return -1;
    } else {
      type = 1;
      bool found = false;
      for (int length = rng.integer(3) + 2; length > 0; length--) {
        int end = length * 5 - 1;
        if (dir == NORTH)
          b = {0, 0, -end, 2, 2, 0};
        else if (dir == SOUTH)
          b = {0, 0, 0, 2, 2, end};
        else if (dir == WEST)
          b = {-end, 0, 0, 0, 2, 2};
        else
          b = {0, 0, 0, end, 2, 2};
        b.move(x, y, z);
        if (!collides(b)) {
          found = true;
          break;
        }
      }
      if (!found)
        return -1;
      bool rails = rng.integer(3) == 0;
      bool spider = !rails && rng.integer(23) == 0;
      flags = int(rails) | (int(spider) << 1);
    }
    int id = add({b, type, dir, depth + 1, flags});
    if (id >= 0)
      children(id);
    return id;
  }
  MHD void entrance(Box b) {
    if (ne == ENTRY_CAP) {
      overflow = true;
      return;
    }
    entries[ne++] = b;
  }
  MHD void children(int id) {
    Piece q = p[id];
    Box b = q.b;
    int d = q.depth, dir = q.dir;
    if (q.type == 0) {
      int height = b.y1 - b.y0 - 3;
      if (height <= 0)
        height = 1;
      for (int side = 0; side < 4; side++) {
        int span = side < 2 ? b.x1 - b.x0 + 1 : b.z1 - b.z0 + 1;
        for (int pos = 0; pos < span; pos += 4) {
          pos += rng.integer(span);
          if (pos + 3 > span)
            break;
          int y = b.y0 + rng.integer(height) + 1, childId;
          if (side == 0)
            childId = child(b.x0 + pos, y, b.z0 - 1, NORTH, d);
          else if (side == 1)
            childId = child(b.x0 + pos, y, b.z1 + 1, SOUTH, d);
          else if (side == 2)
            childId = child(b.x0 - 1, y, b.z0 + pos, WEST, d);
          else
            childId = child(b.x1 + 1, y, b.z0 + pos, EAST, d);
          if (childId >= 0) {
            Box c = p[childId].b;
            if (side == 0)
              entrance({c.x0, c.y0, b.z0, c.x1, c.y1, b.z0 + 1});
            else if (side == 1)
              entrance({c.x0, c.y0, b.z1 - 1, c.x1, c.y1, b.z1});
            else if (side == 2)
              entrance({b.x0, c.y0, c.z0, b.x0 + 1, c.y1, c.z1});
            else
              entrance({b.x1 - 1, c.y0, c.z0, b.x1, c.y1, c.z1});
          }
        }
      }
    } else if (q.type == 1) {
      int end = rng.integer(4), x, z, dd;
      if (dir == NORTH) {
        x = end <= 1 ? b.x0 : (end == 2 ? b.x0 - 1 : b.x1 + 1);
        z = end <= 1 ? b.z0 - 1 : b.z0;
        dd = end <= 1 ? dir : (end == 2 ? WEST : EAST);
      } else if (dir == SOUTH) {
        x = end <= 1 ? b.x0 : (end == 2 ? b.x0 - 1 : b.x1 + 1);
        z = end <= 1 ? b.z1 + 1 : b.z1 - 3;
        dd = end <= 1 ? dir : (end == 2 ? WEST : EAST);
      } else if (dir == WEST) {
        x = end <= 1 ? b.x0 - 1 : b.x0;
        z = end <= 1 ? b.z0 : (end == 2 ? b.z0 - 1 : b.z1 + 1);
        dd = end <= 1 ? dir : (end == 2 ? NORTH : SOUTH);
      } else {
        x = end <= 1 ? b.x1 + 1 : b.x1 - 3;
        z = end <= 1 ? b.z0 : (end == 2 ? b.z0 - 1 : b.z1 + 1);
        dd = end <= 1 ? dir : (end == 2 ? NORTH : SOUTH);
      }
      int y = b.y0 - 1 + rng.integer(3);
      child(x, y, z, dd, d);
      if (d < 8) {
        if (dir == NORTH || dir == SOUTH) {
          for (z = b.z0 + 3; z + 3 <= b.z1; z += 5) {
            int v = rng.integer(5);
            if (v == 0)
              child(b.x0 - 1, b.y0, z, WEST, d + 1);
            else if (v == 1)
              child(b.x1 + 1, b.y0, z, EAST, d + 1);
          }
        } else {
          for (x = b.x0 + 3; x + 3 <= b.x1; x += 5) {
            int v = rng.integer(5);
            if (v == 0)
              child(x, b.y0, b.z0 - 1, NORTH, d + 1);
            else if (v == 1)
              child(x, b.y0, b.z1 + 1, SOUTH, d + 1);
          }
        }
      }
    } else if (q.type == 2) {
      if (dir == NORTH) {
        child(b.x0 + 1, b.y0, b.z0 - 1, NORTH, d);
        child(b.x0 - 1, b.y0, b.z0 + 1, WEST, d);
        child(b.x1 + 1, b.y0, b.z0 + 1, EAST, d);
      } else if (dir == SOUTH) {
        child(b.x0 + 1, b.y0, b.z1 + 1, SOUTH, d);
        child(b.x0 - 1, b.y0, b.z0 + 1, WEST, d);
        child(b.x1 + 1, b.y0, b.z0 + 1, EAST, d);
      } else if (dir == WEST) {
        child(b.x0 + 1, b.y0, b.z0 - 1, NORTH, d);
        child(b.x0 + 1, b.y0, b.z1 + 1, SOUTH, d);
        child(b.x0 - 1, b.y0, b.z0 + 1, WEST, d);
      } else {
        child(b.x0 + 1, b.y0, b.z0 - 1, NORTH, d);
        child(b.x0 + 1, b.y0, b.z1 + 1, SOUTH, d);
        child(b.x1 + 1, b.y0, b.z0 + 1, EAST, d);
      }
      if (q.flags) {
        if (rng.bits(1))
          child(b.x0 + 1, b.y0 + 4, b.z0 - 1, NORTH, d);
        if (rng.bits(1))
          child(b.x0 - 1, b.y0 + 4, b.z0 + 1, WEST, d);
        if (rng.bits(1))
          child(b.x1 + 1, b.y0 + 4, b.z0 + 1, EAST, d);
        if (rng.bits(1))
          child(b.x0 + 1, b.y0 + 4, b.z1 + 1, SOUTH, d);
      }
    } else {
      if (dir == NORTH)
        child(b.x0, b.y0, b.z0 - 1, NORTH, d);
      else if (dir == SOUTH)
        child(b.x0, b.y0, b.z1 + 1, SOUTH, d);
      else if (dir == WEST)
        child(b.x0 - 1, b.y0, b.z0, WEST, d);
      else
        child(b.x1 + 1, b.y0, b.z0, EAST, d);
    }
  }
  MHD bool generate(uint64_t seed, int cx, int cz) {
    n = ne = 0;
    overflow = false;
    roomPruned = false;
    rng.large(seed, cx, cz);
    rng.real(); // Consume the placement draw before constructing the layout.
    int x = cx * 16 + 2, z = cz * 16 + 2;
    int mx = x + 7 + rng.integer(6), my = 54 + rng.integer(6),
        mz = z + 7 + rng.integer(6);
    add({{x, 50, z, mx, my, mz}, 0, -1, 0, 0});
    children(0);
    if (overflow)
      return false;
    int lo = 1000000, hi = -1000000;
    for (int i = 0; i < n; i++) {
      if (p[i].b.y0 < lo)
        lo = p[i].b.y0;
      if (p[i].b.y1 > hi)
        hi = p[i].b.y1;
    }
    int target = hi - lo + 1 - 63;
    if (target < 53)
      target += rng.integer(53 - target);
    int dy = target - hi;
    for (int i = 0; i < n; i++)
      p[i].b.move(0, dy, 0);
    for (int i = 0; i < ne; i++)
      entries[i].move(0, dy, 0);
    return true;
  }
};
} // namespace mine26
#undef MHD
namespace mine26 {
#ifdef __CUDACC__
#define MHD __host__ __device__
#else
#define MHD
#endif
MHD inline int floorDiv(int x, int n) {
  int q = x / n;
  return q - (x < 0 && x % n != 0);
}
MHD inline void hutPosition(uint64_t seed, int rx, int rz, int &x, int &z) {
  LCG r;
  r.seed(seed + uint64_t(int64_t(rx)) * 341873128712ULL +
         uint64_t(int64_t(rz)) * 132897987541ULL + HUT_SALT);
  x = (rx * HUT_SPACING + r.integer(HUT_SPACING - HUT_SEPARATION)) * 16;
  z = (rz * HUT_SPACING + r.integer(HUT_SPACING - HUT_SEPARATION)) * 16;
}
MHD inline bool nearbyHut(uint64_t seed, int cx, int cz) {
  int x0 = cx * 16 + 2 - 100, x1 = cx * 16 + 2 + 100, z0 = cz * 16 + 2 - 100,
      z1 = cz * 16 + 2 + 100;
  for (int rz = floorDiv(z0 - 8, HUT_SPACING * 16);
       rz <= floorDiv(z1, HUT_SPACING * 16); rz++)
    for (int rx = floorDiv(x0 - 8, HUT_SPACING * 16);
         rx <= floorDiv(x1, HUT_SPACING * 16); rx++) {
      int x, z;
      hutPosition(seed, rx, rz, x, z);
      if (x <= x1 && x + 8 >= x0 && z <= z1 && z + 8 >= z0)
        return true;
    }
  return false;
}
MHD inline bool canClearAt(const Layout &g, int id, int x, int y, int z,
                           int originX, int originZ) {
  const Piece &p = g.p[id];
  const Box &b = p.b;
  if (p.type == 0)
    for (int j = 0; j < g.ne; j++) {
      const Box &e = g.entries[j];
      if (x >= e.x0 && x <= e.x1 && z >= e.z0 && z <= e.z1 && y >= e.y1 - 2 &&
          y <= e.y1)
        return true;
    }
  if (x < b.x0 || x > b.x1 || y < b.y0 || y > b.y1 || z < b.z0 || z > b.z1)
    return false;
  // Vanilla's room has no orientation: generateUpperHalfSphere uses absolute
  // coordinates in float arithmetic. Translation is NOT invariant far out.
  if (p.type == 0) {
    if (y >= b.y0 + 1 && y <= b.y0 + 3)
      return true;
    if (y < b.y0 + 4)
      return false;
    float dx = b.x1 - b.x0 + 1, dy = b.y1 - b.y0 - 3, dz = b.z1 - b.z0 + 1;
    float nx = (float(x + originX) - (float(b.x0 + originX) + dx / 2.f)) /
               (dx * .5f),
          ny = (y - (b.y0 + 4)) / dy,
          nz = (float(z + originZ) - (float(b.z0 + originZ) + dz / 2.f)) /
               (dz * .5f);
    return nx * nx + ny * ny + nz * nz <= 1.05f;
  }
  if (p.type == 1)
    return true;
  if (p.type == 2) {
    bool ix = x > b.x0 && x<b.x1, iz = z> b.z0 && z < b.z1;
    if (b.y1 - b.y0 + 1 > 3 && y == b.y0 + 3)
      return ix && iz;
    return ix || iz;
  }
  int zz = p.dir == NORTH   ? b.z1 - z
           : p.dir == SOUTH ? z - b.z0
           : p.dir == WEST  ? b.x1 - x
                            : x - b.x0,
      yy = y - b.y0;
  if (zz <= 1)
    return yy >= 5 && yy <= 7;
  if (zz >= 7)
    return yy <= 2;
  int j = zz - 2;
  return yy >= 5 - j - (j < 4 ? 1 : 0) && yy <= 7 - j;
}
MHD inline bool canClear(const Layout &g, int id, int x, int y, int z) {
  return canClearAt(g, id, x, y, z, 0, 0);
}
struct Hit {
  uint64_t seed;
  int x, z, width, gain53, gain54, covered, pieces;
};
MHD inline bool anyClear(const Layout &g, int x, int y, int z) {
  for (int i = 0; i < g.n; i++)
    if (canClear(g, i, x, y, z))
      return true;
  return false;
}
MHD inline int hits(const Layout &g, uint64_t seed, Hit *out, int capacity) {
  int x0 = g.p[0].b.x0, x1 = g.p[0].b.x1, z0 = g.p[0].b.z0, z1 = g.p[0].b.z1,
      y0 = g.p[0].b.y0;
  for (int i = 1; i < g.n; i++) {
    const Box &b = g.p[i].b;
    if (b.x0 < x0)
      x0 = b.x0;
    if (b.x1 > x1)
      x1 = b.x1;
    if (b.z0 < z0)
      z0 = b.z0;
    if (b.z1 > z1)
      z1 = b.z1;
    if (b.y0 < y0)
      y0 = b.y0;
  }
  if (y0 > -54)
    return 0;
  int n = 0;
  for (int rz = floorDiv(z0 - 8, HUT_SPACING * 16);
       rz <= floorDiv(z1, HUT_SPACING * 16); rz++)
    for (int rx = floorDiv(x0 - 8, HUT_SPACING * 16);
         rx <= floorDiv(x1, HUT_SPACING * 16); rx++) {
      int x, z;
      hutPosition(seed, rx, rz, x, z);
      if (x > x1 || x + 8 < x0 || z > z1 || z + 8 < z0)
        continue;
      LCG r;
      r.large(seed, x / 16, z / 16);
      int width = (r.integer(4) & 1) ? 9 : 7, depth = 63 / width, g53 = 0,
          g54 = 0, covered = 0;
      for (int zz = z; zz < z + depth; zz++)
        for (int xx = x; xx < x + width; xx++) {
          int a = -53, b = -54;
          while (a > -64 && anyClear(g, xx, a - 1, zz))
            a--;
          while (b > -64 && anyClear(g, xx, b - 1, zz))
            b--;
          g53 += -53 - a;
          g54 += -54 - b;
          if (a < -53 || b < -54)
            covered++;
        }
      if (g53 >= 126 || g54 >= 63) {
        if (n < capacity)
          out[n] = {seed, x, z, width, g53, g54, covered, g.n};
        n++;
      }
    }
  return n;
}
#undef MHD
} // namespace mine26
