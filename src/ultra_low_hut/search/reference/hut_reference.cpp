#include <cstddef>
#include <cstdint>
extern "C" {
#include "column_top.h"
#include "eval.h"
lysh_hut_result ms_screen_hut(lysh_search_ctx *, int, int, int);
}
#include "hut_versions.generated.h"
#include "layout_probe_plan.h"
#include "mine_layout26.h"
#include <cstring>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>
static int eval_column_top_cb(void *v, int x, int z) {
  return lysh_preliminary_surface_level((const lysh_terrain *)v, x, z);
}
// Initialize the terrain and biome state used by hut queries.
static void terrain_context_init(lysh_search_ctx *ctx, uint64_t seed,
                                 const lysh_phase1_opts *opts, int max_height) {
  memset(ctx, 0, sizeof(*ctx));
  ctx->seed = seed;
  if (opts)
    ctx->opts = *opts;
  ctx->max_height = max_height;
  ctx->large_biomes = ctx->opts.large_biomes;
  lysh_phase2_init(&ctx->p2, seed, ctx->large_biomes);
  lysh_phase2_set_column_top(&ctx->p2, eval_column_top_cb, &ctx->p2.terrain);
  lysh_phase2_set_carvers(&ctx->p2, 1);
  int tree = ctx->opts.pre_26_2 ? LYSH_BIOME_TREE_1_21_5 : LYSH_BIOME_TREE_26_2;
  lysh_biome_init(&ctx->biome, seed, ctx->large_biomes, tree);
  ctx->inited = 1;
}

static thread_local std::string error;
struct Context {
  lysh_search_ctx hut;
  lysh_phase1_opts opts{};
};
extern "C" const char *ms_error() { return error.c_str(); }
extern "C" void *ms_open_world(uint64_t seed, const char *version, int device,
                                int world_type, int swamp_biome) {
  try {
    if (device != -1)
      throw std::runtime_error(
          "Terrain reference uses the CPU; pass device=-1");
    auto c = std::make_unique<Context>();
    std::string v = version;
    const HutVersionConfig *config = nullptr;
    for (const auto &entry : hutVersionConfigs)
      if (v == entry.name) {
        config = &entry;
        break;
      }
    if (!config)
      throw std::runtime_error(
          "unsupported version; see config/versions/profiles.json");

    if (world_type < 0 || world_type > 2)
      throw std::runtime_error("unsupported world type");
    c->opts.pre_26_2 = config->pre262;
    c->opts.large_biomes = world_type == 1;
    // 1: fixed swamp; 2: another fixed biome (no vanilla swamp huts).
    c->opts.single_biome = world_type == 2 ? (swamp_biome ? 1 : 2) : 0;
    // Terrain columns are generated lazily when queried.
    terrain_context_init(&c->hut, seed, &c->opts, -40);
    return c.release();
  } catch (const std::exception &e) {
    error = e.what();
    return nullptr;
  }
}
extern "C" void *ms_open(uint64_t seed, const char *version, int device) {
  return ms_open_world(seed, version, device, 0, 0);
}
extern "C" void ms_close(void *v) {
  auto c = static_cast<Context *>(v);
  if (!c)
    return;
  lysh_search_ctx_free(&c->hut);
  delete c;
}
#define GUARD_BEGIN try {
#define GUARD_END                                                              \
  return 0;                                                                    \
  }                                                                            \
  catch (const std::exception &e) {                                            \
    error = e.what();                                                          \
    return -1;                                                                 \
  }
extern "C" int ms_hut(void *v, int x, int z, int max_y, int *out) {
  GUARD_BEGIN
  auto c = static_cast<Context *>(v);
  auto r = lysh_eval_hut(&c->hut, x, z, max_y);
  out[0] = r.avg_y;
  out[1] = r.ok;
  out[2] = r.biome_winner;
  out[3] = r.wet_columns;
  out[4] = r.dir;
  GUARD_END
}
extern "C" int ms_hut_screen(void *v, int x, int z, int max_y, int *out) {
  GUARD_BEGIN
  auto c = static_cast<Context *>(v);
  auto r = ms_screen_hut(&c->hut, x, z, max_y);
  out[0] = r.avg_y;
  out[1] = r.ok;
  out[2] = r.biome_winner;
  out[3] = r.wet_columns;
  out[4] = r.dir;
  GUARD_END
}
// Mineshaft geometry used by the layout budget gate.
extern "C" int ms_room_box(uint64_t target, int *out) {
  GUARD_BEGIN
  mine26::Layout layout;
  if (!layout.generate(target, 0, 0))
    throw std::runtime_error("mineshaft layout overflow");
  auto b = layout.p[0].b;
  int values[6] = {b.x0, b.y0, b.z0, b.x1, b.y1, b.z1};
  std::memcpy(out, values, sizeof(values));
  GUARD_END
}
extern "C" int ms_room_corner_gate(void *v, int x, int z, const int *b,
                                   int *passed) {
  GUARD_BEGIN
  auto c = static_cast<Context *>(v);

  *passed = 1;
  if (-55 >= b[1] - 1 && -55 <= b[4] + 1)
    for (int corner = 0; corner < 4; corner++) {
      int xx = x + ((corner & 1) ? b[3] + 1 : b[0] - 1),
          zz = z + ((corner & 2) ? b[5] + 1 : b[2] - 1);
      auto state = lysh_phase2_block_at(&c->hut.p2, xx, -55, zz);
      if (state == LYSH_BLOCK_WATER || state == LYSH_BLOCK_LAVA) {
        *passed = 0;
        break;
      }
    }
  GUARD_END
}
// relX/relZ locate the hut anchor relative to the mineshaft starting chunk.
// Clearing is optimistic: piece vetoes,
// probabilistic corridor roofs and replacement/support blocks are omitted.
extern "C" int ms_room_masks_for_hut(uint64_t target, int hutX, int hutZ,
                                     int width, int relX, int relZ,
                                     uint32_t *out) {
  GUARD_BEGIN
  if (width != 7 && width != 9)
    throw std::runtime_error("hut width must be 7 or 9");
  const int originX = hutX - relX, originZ = hutZ - relZ;
  mine26::Layout layout;
  if (!layout.generate(target, 0, 0))
    throw std::runtime_error("mineshaft layout overflow");
  for (int c = 0; c < 63; c++) {
    out[c] = 0;
    for (int y = -64; y < -32; y++)
      for (int piece = 0; piece < layout.n; piece++)
        if (mine26::canClearAt(layout, piece, relX + c % width, y,
                               relZ + c / width, originX, originZ)) {
          out[c] |= uint32_t(1) << (y + 64);
          break;
        }
  }
  GUARD_END
}
extern "C" int ms_room_masks_at(uint64_t target, int originX, int originZ,
                                uint32_t *out) {
  return ms_room_masks_for_hut(target, originX, originZ, 7, 0, 0, out);
}
extern "C" int ms_room_masks(uint64_t target, uint32_t *out) {
  return ms_room_masks_at(target, 0, 0, out);
}
// Six 64-bit words per footprint column, covering the complete build height.
// This optimistic union is used to skip provably zero placement experiments.
extern "C" int ms_mineshaft_clearing_masks(uint64_t target, int hutX, int hutZ,
                                           int width, int relX, int relZ,
                                           uint64_t *out) {
  GUARD_BEGIN
  if (width != 7 && width != 9)
    throw std::runtime_error("hut width must be 7 or 9");
  mine26::Layout layout;
  if (!layout.generate(target, 0, 0))
    throw std::runtime_error("mineshaft layout overflow");
  std::memset(out, 0, 63 * 6 * sizeof(uint64_t));
  for (int c = 0; c < 63; c++) {
    int x = relX + c % width, z = relZ + c / width;
    std::vector<int> overlapping{0};
    for (int piece = 1; piece < layout.n; piece++) {
      const auto &box = layout.p[piece].b;
      if (x >= box.x0 && x <= box.x1 && z >= box.z0 && z <= box.z1)
        overlapping.push_back(piece);
    }
    for (int y = -64; y < 320; y++)
      for (int piece : overlapping)
        if (mine26::canClearAt(layout, piece, x, y, z, hutX - relX,
                               hutZ - relZ)) {
          out[c * 6 + (y + 64) / 64] |= uint64_t(1) << ((y + 64) % 64);
          break;
        }
  }
  GUARD_END
}
// Results: rejection stage (0 pass, 1 geometry, 2 corners, 3 rim), block
// 4 high obstruction; probes, current optimistic footprint-height sum. This is
// a discovery heuristic on pre-feature terrain, not a necessary condition in
// full worlds. The room box and column masks are relative to the actual hut
// anchor.
extern "C" int ms_room_budget_gate_footprint(void *v, int x, int z,
                                             const int *b,
                                             const uint32_t *masks, int width,
                                             int target, int *out) {
  GUARD_BEGIN
  auto c = static_cast<Context *>(v);

  if (target > -55 || target < -60)
    throw std::runtime_error("invalid room budget target");
  if (width != 7 && width != 9)
    throw std::runtime_error("hut width must be 7 or 9");
  int lower[63], sum = 0, probes = 0, status = 0;
#ifdef HUT_COMPILED_LAYOUT_PROBES
  const auto &plan = layout_probes::cached(b, masks, width, target);
  auto compiled_lower = plan.lower;
  sum = plan.initial_sum;
  if (sum > plan.target_sum)
    status = 1;
  for (const auto &probe : plan.probes) {
    if (status)
      break;
    if (probe.operation == layout_probes::Operation::RaiseColumn &&
        probe.y + 1 <= compiled_lower[probe.column])
      continue;
    auto state =
        lysh_phase2_block_at(&c->hut.p2, x + probe.x, probe.y, z + probe.z);
    ++probes;
    if (probe.operation == layout_probes::Operation::RequireAir) {
      if (state != LYSH_BLOCK_AIR)
        status = 4;
    } else if (probe.operation == layout_probes::Operation::RejectFluid) {
      if (state == LYSH_BLOCK_WATER || state == LYSH_BLOCK_LAVA)
        status = 2;
    } else if (state != LYSH_BLOCK_AIR) {
      sum += probe.y + 1 - compiled_lower[probe.column];
      compiled_lower[probe.column] = probe.y + 1;
      if (sum > plan.target_sum)
        status = 3;
    }
  }
  out[0] = status;
  out[1] = probes;
  out[2] = sum;
  return 0;
#endif
  for (int col = 0; col < 63; col++) {
    int y = -54;
    while (y > -64 && (masks[col] & (uint32_t(1) << (y + 63))))
      y--;
    lower[col] = y;
    sum += y;
  }
  if (sum > target * 63)
    status = 1;
  if (!status && b[1] == -62 && b[4] + 1 < -55) {
    int xs[3] = {b[0] - 1, (b[0] + b[3]) / 2, b[3] + 1};
    int zs[3] = {b[2] - 1, (b[2] + b[5]) / 2, b[5] + 1};
    for (int xx : xs)
      for (int zz : zs) {
        if (status)
          break;
        auto state = lysh_phase2_block_at(&c->hut.p2, x + xx, b[4] + 1, z + zz);
        probes++;
        if (state == LYSH_BLOCK_WATER || state == LYSH_BLOCK_LAVA)
          status = 2;
      }
  }
  if (!status && -55 >= b[1] - 1 && -55 <= b[4] + 1)
    for (int corner = 0; corner < 4; corner++) {
      auto state = lysh_phase2_block_at(
          &c->hut.p2, x + ((corner & 1) ? b[3] + 1 : b[0] - 1), -55,
          z + ((corner & 2) ? b[5] + 1 : b[2] - 1));
      probes++;
      if (state == LYSH_BLOCK_WATER || state == LYSH_BLOCK_LAVA) {
        status = 2;
        break;
      }
    }
  if (!status && b[1] == -62) {
    auto state = lysh_phase2_block_at(&c->hut.p2, x + 3, 62, z + 3);
    probes++;
    if (state != LYSH_BLOCK_AIR)
      status = 4;
  }
  for (int col = 0; col < 63 && !status; col++)
    for (int y : {-54, -53, -52, -48}) {
      if (y + 1 <= lower[col] || (masks[col] & (uint32_t(1) << (y + 64))))
        continue;
      auto state =
          lysh_phase2_block_at(&c->hut.p2, x + col % width, y, z + col / width);
      probes++;
      if (state != LYSH_BLOCK_AIR) {
        sum += y + 1 - lower[col];
        lower[col] = y + 1;
        if (sum > target * 63) {
          status = 3;
          break;
        }
      }
    }
  out[0] = status;
  out[1] = probes;
  out[2] = sum;
  GUARD_END
}

extern "C" int ms_room_budget_gate(void *v, int x, int z, const int *b,
                                   const uint32_t *masks, int target,
                                   int *out) {
  return ms_room_budget_gate_footprint(v, x, z, b, masks, 7, target, out);
}

extern "C" int ms_terrain_probe(void *v, int x, int z, int *out) {
  GUARD_BEGIN
  auto c = static_cast<Context *>(v);
  out[0] = lysh_preliminary_surface_level(&c->hut.p2.terrain, x, z);
  out[1] = lysh_phase2_height(&c->hut.p2, x, z);
  GUARD_END
}

extern "C" lysh_block_state ms_post_carver_block(lysh_phase2 *, int, int, int);
// Only scan above the bedrock band. The reference terrain does not model
// surface-stage bedrock replacement; this is a partial liquid-veto check.
extern "C" int ms_room_upper_fluid_gate(void *v, int x, int z, const int *b,
                                        int *out) {
  GUARD_BEGIN
  auto c = static_cast<Context *>(v);
  int x0 = std::max(0, b[0] - 1), x1 = std::min(15, b[3] + 1),
      z0 = std::max(0, b[2] - 1), z1 = std::min(15, b[5] + 1);
  int bottom = std::max(-64, b[1] - 1), y0 = std::max(-59, bottom),
      y1 = std::min(319, b[4] + 1);
  out[0] = 1;
  out[1] = 0;
  out[2] = out[3] = out[4] = 0;
  for (int zz = z0; zz <= z1; zz++)
    for (int xx = x0; xx <= x1; xx++)
      for (int yy = y0; yy <= y1; yy++) {
        if (xx != x0 && xx != x1 && zz != z0 && zz != z1 && yy != y1 &&
            yy != bottom)
          continue;
        auto state = ms_post_carver_block(&c->hut.p2, x + xx, yy, z + zz);
        out[1]++;
        if (state == LYSH_BLOCK_WATER || state == LYSH_BLOCK_LAVA) {
          out[0] = 0;
          out[2] = xx;
          out[3] = yy;
          out[4] = zz;
          return 0;
        }
      }
  GUARD_END
}
