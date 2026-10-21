import com.google.gson.*;
import java.io.*;
import java.nio.file.*;
import java.util.*;
public final class LayoutYieldService {
  static JsonObject cohortModel(JsonObject layout, JsonObject cohort,
                                int region) {
    int[] origins = {0, 12582912, 20000000};
    JsonArray origin =
        layout.has("test_origin") ? layout.getAsJsonArray("test_origin") : null;
    JsonObject model = new JsonObject();
    model.addProperty("origin_x", origin != null ? origin.get(0).getAsInt()
                                                 : origins[region / 3]);
    model.addProperty("origin_z", origin != null ? origin.get(1).getAsInt()
                                                 : origins[region % 3]);
    model.add("mine_target", layout.get("target"));
    model.addProperty("hut_width",
                      layout.has("width") ? layout.get("width").getAsInt() : 7);
    model.add("snapshot_file", cohort.get("snapshot_file"));
    if (cohort.has("natural_biomes") &&
        cohort.get("natural_biomes").getAsBoolean()) {
      model.addProperty("natural_biomes", true);
      model.add("source_seed", cohort.get("seed"));
      model.add("source_x", cohort.get("x"));
      model.add("source_z", cohort.get("z"));
    }
    model.addProperty("cache_terrain", true);
    model.addProperty("decoration_seed", 0);
    JsonObject request = new JsonObject();
    request.add("seed", cohort.get("seed"));
    request.add("controlled_model", model);
    return request;
  }

  static JsonObject measure(JsonObject job, JsonArray cohorts)
      throws Exception {
    JsonObject layout = job.getAsJsonObject("layout");
    int region = job.get("region").getAsInt(), n = job.get("n").getAsInt();
    Random draw = new Random(job.get("sampling_seed").getAsLong());
    int hits = 0, h58 = 0, h60 = 0, minimumHeight = 320, veto = 0;
    long start = System.nanoTime();
    int[] perN = new int[cohorts.size()], perK = new int[cohorts.size()];
    for (int j = 0; j < n; j++) {
      int ti = 0, cumulative = 0;
      JsonArray counts = job.getAsJsonArray("counts");
      while (ti < counts.size() &&
             j >= cumulative + counts.get(ti).getAsInt()) {
        cumulative += counts.get(ti).getAsInt();
        ti++;
      }
      if (ti >= cohorts.size())
        throw new IllegalStateException("counts mismatch");
      JsonObject c = cohorts.get(ti).getAsJsonObject();
      JsonObject request = cohortModel(layout, c, region);
      request.getAsJsonObject("controlled_model")
          .addProperty("decoration_seed", draw.nextLong());
      JsonObject v =
          LayoutPlacementReplay.run(VanillaQueryMain.server, request);
      if (v.get("actual_room_bottom").getAsInt() !=
              layout.get("room_bottom").getAsInt() ||
          v.get("layout_pieces").getAsInt() != layout.get("pieces").getAsInt())
        throw new IllegalStateException("layout parity failure");
      JsonArray box = v.getAsJsonArray("room_box"),
                dims = layout.getAsJsonArray("dimensions");
      for (int i = 0; i < 3; i++)
        if (box.get(i + 3).getAsInt() - box.get(i).getAsInt() + 1 !=
            dims.get(i).getAsInt())
          throw new IllegalStateException("dimension parity failure");
      int h = v.getAsJsonArray("heights").get(0).getAsInt();
      minimumHeight = Math.min(minimumHeight, h);
      if (h <= -60)
        h60++;
      boolean hit = h <= -59;
      if (hit)
        hits++;
      if (h <= -58)
        h58++;
      perN[ti]++;
      if (hit)
        perK[ti]++;
      if (v.get("room_veto").getAsBoolean())
        veto++;
    }
    JsonObject out = new JsonObject();
    out.add("target", layout.get("target"));
    out.addProperty("region", region);
    out.addProperty("n", n);
    out.addProperty("hits59", hits);
    out.addProperty("hits58", h58);
    out.addProperty("hits60", h60);
    out.addProperty("minimum_height", minimumHeight);
    out.addProperty("room_veto", veto);
    out.addProperty("seconds", (System.nanoTime() - start) * 1e-9);
    JsonArray strata = new JsonArray();
    for (int i = 0; i < cohorts.size(); i++) {
      JsonObject t = new JsonObject();
      t.add("terrain", cohorts.get(i).getAsJsonObject().get("id"));
      t.addProperty("n", perN[i]);
      t.addProperty("hits59", perK[i]);
      strata.add(t);
    }
    out.add("perTerrain", strata);
    return out;
  }
  public static void main(String[] args) throws Exception {
    JsonArray cohorts =
        JsonParser.parseString(Files.readString(Path.of(args[0])))
            .getAsJsonArray();
    VanillaQueryMain.bootstrap();
    VanillaQueryMain.server =
        VanillaQueryMain.createWorldContext(0, "minecraft:swamp");
    BufferedWriter out = new BufferedWriter(
        new OutputStreamWriter(new FileOutputStream(FileDescriptor.out)));
    out.write("{\"ready\":true}\n");
    out.flush();
    try (out; BufferedReader in =
                  new BufferedReader(new InputStreamReader(System.in))) {
      String line;
      while ((line = in.readLine()) != null) {
        JsonObject r =
            measure(JsonParser.parseString(line).getAsJsonObject(), cohorts);
        out.write(r.toString());
        out.newLine();
        out.flush();
      }
    }
    System.exit(0);
  }
}
