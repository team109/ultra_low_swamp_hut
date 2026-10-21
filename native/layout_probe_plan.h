#pragma once

#include <algorithm>
#include <array>
#include <cstdint>
#include <map>
#include <vector>

namespace layout_probes {

enum class Operation { RequireAir, RejectFluid, RaiseColumn };
struct Probe {
  Operation operation;
  int x, y, z, column;
};
struct Plan {
  int initial_sum;
  int target_sum;
  std::array<int, 63> lower;
  std::vector<Probe> probes;
};

inline Plan compile(const int *box, const uint32_t *masks, int width,
                    int target) {
  Plan plan{};
  plan.target_sum = target * 63;
  for (int column = 0; column < 63; ++column) {
    int y = -54;
    while (y > -64 && (masks[column] & (uint32_t(1) << (y + 63))))
      --y;
    plan.lower[column] = y;
    plan.initial_sum += y;
  }
  if (box[1] == -62)
    plan.probes.push_back({Operation::RequireAir, 3, 62, 3, -1});
  if (box[1] == -62 && box[4] + 1 < -55) {
    int xs[3] = {box[0] - 1, (box[0] + box[3]) / 2, box[3] + 1};
    int zs[3] = {box[2] - 1, (box[2] + box[5]) / 2, box[5] + 1};
    for (int x : xs)
      for (int z : zs)
        plan.probes.push_back({Operation::RejectFluid, x, box[4] + 1, z, -1});
  }
  if (-55 >= box[1] - 1 && -55 <= box[4] + 1)
    for (int corner = 0; corner < 4; ++corner)
      plan.probes.push_back({Operation::RejectFluid,
                             (corner & 1) ? box[3] + 1 : box[0] - 1, -55,
                             (corner & 2) ? box[5] + 1 : box[2] - 1, -1});
  std::vector<Probe> rim;
  for (int column = 0; column < 63; ++column)
    for (int y : {-54, -53, -52, -48})
      if (y + 1 > plan.lower[column] &&
          !(masks[column] & (uint32_t(1) << (y + 64))))
        rim.push_back({Operation::RaiseColumn, column % width, y,
                       column / width, column});
  std::stable_sort(rim.begin(), rim.end(), [&](const Probe &a, const Probe &b) {
    return a.y + 1 - plan.lower[a.column] > b.y + 1 - plan.lower[b.column];
  });
  plan.probes.insert(plan.probes.end(), rim.begin(), rim.end());
  return plan;
}

inline const Plan &cached(const int *box, const uint32_t *masks, int width,
                          int target) {
  std::array<uint32_t, 71> key{};
  for (int i = 0; i < 6; ++i)
    key[i] = uint32_t(box[i]);
  for (int i = 0; i < 63; ++i)
    key[i + 6] = masks[i];
  key[69] = uint32_t(width);
  key[70] = uint32_t(target);
  static thread_local std::map<decltype(key), Plan> plans;
  auto found = plans.find(key);
  if (found == plans.end())
    found = plans.emplace(key, compile(box, masks, width, target)).first;
  return found->second;
}

} // namespace layout_probes
