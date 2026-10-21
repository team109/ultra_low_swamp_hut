"""Generate a phase-2 cache that evaluates interpolation nodes on demand."""

import sys
from pathlib import Path

source = Path(sys.argv[1]).read_text()
start = source.index("static void ensure_cell_cache(")
end = source.index("\n/*", start)
source = (
    source[:start]
    + """static void ensure_cell_cache(lysh_phase2 *p2, int cell_x, int cell_z, int cell_y) {
    int base_x = cell_x & ~3, base_z = cell_z & ~3;
    if (p2->cell_col_x != base_x || p2->cell_col_z != base_z) {
        p2->cell_col_x = base_x;
        p2->cell_col_z = base_z;
        p2->cell_col_valid = 0;
    }
    int gx0 = cell_x - base_x, gz0 = cell_z - base_z;
    for (int dx = 0; dx < 2; dx++) for (int dz = 0; dz < 2; dz++) {
        int idx = (gx0 + dx) * 5 + gz0 + dz;
        if (!(p2->cell_col_valid & (1u << idx))) {
            // Noise samples are finite; NaN marks an unevaluated cache node.
            for (int j = 0; j <= p2->vertical_block_count; j++)
                p2->cell_col_main[idx][j] = NAN;
            p2->cell_col_valid |= 1u << idx;
        }
        int bx = (base_x + gx0 + dx) * p2->horizontal_block_size;
        int bz = (base_z + gz0 + dz) * p2->horizontal_block_size;
        lysh_terrain_info ti;
        int terrain_ready = 0;
        for (int j = cell_y; j <= cell_y + 1; j++) {
            if (!isnan(p2->cell_col_main[idx][j])) continue;
            if (!terrain_ready) {
                lysh_terrain_info_at(&p2->terrain, bx >> 2, bz >> 2, &ti);
                terrain_ready = 1;
            }
            int y = p2->minimum_y + j * p2->vertical_block_size;
            double base = lysh_interp_calculate_noise_261(&p2->interp, bx, y, bz);
            p2->cell_col_main[idx][j] = lysh_sample_noise_column(
                &p2->density, bx, y, bz, &ti.point, base, 1, 0);
            p2->cell_col_noodle[0][idx][j] = lysh_noodle_child(
                &p2->density, LYSH_NOODLE_THICKNESS, bx, y, bz);
            p2->cell_col_noodle[1][idx][j] = lysh_noodle_child(
                &p2->density, LYSH_NOODLE_RIDGE_A, bx, y, bz);
            p2->cell_col_noodle[2][idx][j] = lysh_noodle_child(
                &p2->density, LYSH_NOODLE_RIDGE_B, bx, y, bz);
        }
    }
}
"""
    + source[end:]
)
anchor = "ensure_cell_cache(p2, cell_x, cell_z);"
assert source.count(anchor) == 1
source = source.replace(anchor, "ensure_cell_cache(p2, cell_x, cell_z, cell_y);")
Path(sys.argv[2]).write_text(source)
