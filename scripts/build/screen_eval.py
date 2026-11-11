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
biome_call = """lysh_swamp_hut_biome_ok(&ctx->biome, &ctx->p2.terrain, hut_x, hut_z,
                            eval_biome_height_cb, &ctx->p2, &br);"""
assert source.count(biome_call) == 1
source = source.replace(
    biome_call,
    """if (ctx->opts.single_biome) {
        memset(&br, 0, sizeof(br));
        br.ok = ctx->opts.single_biome == 1;
        br.winner = br.ok ? 6 : -1;
    } else {
        """ + biome_call + "\n    }",
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
