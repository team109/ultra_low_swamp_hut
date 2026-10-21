"""Add an acceptance-only entry point while preserving diagnostic evaluation."""

import sys
from pathlib import Path

source = Path(sys.argv[1]).read_text()
old = "lysh_hut_result lysh_eval_hut(lysh_search_ctx *ctx, int hut_x, int hut_z, int max_y) {"
assert source.count(old) == 1
source = source.replace(
    old,
    "static lysh_hut_result evaluate(lysh_search_ctx *ctx, int hut_x, int hut_z, int max_y, int screening) {",
)
anchor = "r.biome_occ_y = br.target.occ_y;"
assert source.count(anchor) == 1
source = source.replace(
    anchor,
    anchor
    + """
    if (screening && !r.biome_ok) {
        r.reject = LYSH_HUT_REJECT_BIOME;
        return r;
    }""",
)
anchor = "r.all_dry = (wet == 0);"
assert source.count(anchor) == 1
source = source.replace(
    anchor,
    anchor
    + """
    if (screening && r.flooded) {
        r.reject = LYSH_HUT_REJECT_FLOOD;
        return r;
    }""",
)
source += """
lysh_hut_result lysh_eval_hut(lysh_search_ctx *ctx,int x,int z,int max_y) {
    return evaluate(ctx,x,z,max_y,0);
}
lysh_hut_result ms_screen_hut(lysh_search_ctx *ctx,int x,int z,int max_y) {
    return evaluate(ctx,x,z,max_y,1);
}
"""
output = Path(sys.argv[2])
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(source)
