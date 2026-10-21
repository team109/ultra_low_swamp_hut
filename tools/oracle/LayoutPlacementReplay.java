import com.google.gson.*;
import java.lang.reflect.*;
import java.util.*;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.Registries;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.*;
import net.minecraft.world.level.biome.Biomes;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.chunk.*;
import net.minecraft.world.level.levelgen.*;
import net.minecraft.world.level.levelgen.structure.*;
import net.minecraft.world.level.levelgen.structure.pieces.StructurePiecesBuilder;
import net.minecraft.world.level.levelgen.structure.structures.*;
/** Vanilla structure placement on a supplied controlled terrain snapshot. */
public final class LayoutPlacementReplay {
  static final Map<String, BlockState[]> terrainCache =
      new LinkedHashMap<String, BlockState[]>(32, .75f, true) {
        protected boolean removeEldestEntry(
            Map.Entry<String, BlockState[]> entry) {
          return size() > 32;
        }
      };

  static final class Terrain implements InvocationHandler {
    final int originX, originZ, hutWidth;
    final ServerLevel level;
    final BlockState[] blocks = new BlockState[16 * 16 * 384];
    final ProtoChunk chunk;
    final RandomSource random;
    final Set<String> calls = new TreeSet<>();
    final NaturalBiomeSampler naturalBiomes;
    final int sourceX, sourceZ;
    Terrain(ServerLevel level, JsonObject model) throws Exception {
      this.level = level;
      naturalBiomes = model.has("natural_biomes") &&
                              model.get("natural_biomes").getAsBoolean()
                          ? NaturalBiomeSampler.get(
                                level, model.get("source_seed").getAsLong())
                          : null;
      sourceX = naturalBiomes != null ? model.get("source_x").getAsInt() : 0;
      sourceZ = naturalBiomes != null ? model.get("source_z").getAsInt() : 0;
      hutWidth = model.has("hut_width") ? model.get("hut_width").getAsInt() : 7;
      originX = model.has("origin_x") ? model.get("origin_x").getAsInt() : 0;
      originZ = model.has("origin_z") ? model.get("origin_z").getAsInt() : 0;
      random = new WorldgenRandom(
          new XoroshiroRandomSource(model.get("decoration_seed").getAsLong()));
      chunk = new ProtoChunk(
          new ChunkPos(originX >> 4, originZ >> 4), UpgradeData.EMPTY,
          LevelHeightAccessor.create(-64, 384),
          level.registryAccess().registryOrThrow(Registries.BIOME), null);
      boolean cache = model.has("cache_terrain") &&
                      model.get("cache_terrain").getAsBoolean();
      String key = cache ? model.get("snapshot_file").getAsString() : null;
      BlockState[] baseline = cache ? terrainCache.get(key) : null;
      if (baseline != null)
        System.arraycopy(baseline, 0, blocks, 0, blocks.length);
      else {
        byte[] raw = java.nio.file.Files.readAllBytes(
            java.nio.file.Path.of(model.get("snapshot_file").getAsString()));
        BlockState[] palette = {Blocks.AIR.defaultBlockState(),
                                Blocks.DEEPSLATE.defaultBlockState(),
                                Blocks.WATER.defaultBlockState(),
                                Blocks.LAVA.defaultBlockState(),
                                Blocks.BEDROCK.defaultBlockState()};
        if (raw.length != blocks.length)
          throw new IllegalArgumentException("snapshot length");
        for (int i = 0; i < raw.length; i++)
          blocks[i] = palette[raw[i]];
        if (cache)
          terrainCache.put(key, blocks.clone());
      }
    }

    int index(int x, int y, int z) {
      x -= originX;
      z -= originZ;
      if (x < 0 || x > 15 || z < 0 || z > 15 || y < -64 || y >= 320)
        throw new IllegalArgumentException("outside controlled chunk: " + x +
                                           "," + y + "," + z);
      return ((z * 16 + x) * 384) + (y + 64);
    }
    BlockState block(BlockPos p) {
      if (p.getY() < -64 || p.getY() >= 320)
        return Blocks.AIR.defaultBlockState();
      return blocks[index(p.getX(), p.getY(), p.getZ())];
    }
    int height(Heightmap.Types type, int x, int z) {
      for (int y = 319; y >= -64; y--)
        if (type.isOpaque().test(blocks[index(x, y, z)]))
          return y + 1;
      return -64;
    }
    JsonArray columns() {
      JsonArray a = new JsonArray();
      for (int z = 0; z < 63 / hutWidth; z++)
        for (int x = 0; x < hutWidth; x++)
          a.add(height(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, x + originX,
                       z + originZ));
      return a;
    }
    public Object invoke(Object proxy, Method method, Object[] args)
        throws Throwable {
      String n = method.getName();
      calls.add(n);
      switch (n) {
      case "getBlockState":
        return block((BlockPos)args[0]);
      case "getFluidState":
        return block((BlockPos)args[0]).getFluidState();
      case "setBlock": {
        BlockPos p = (BlockPos)args[0];
        BlockState state = (BlockState)args[1];
        blocks[index(p.getX(), p.getY(), p.getZ())] = state;
        return true;
      }
      case "getBiome":
        if (naturalBiomes != null) {
          BlockPos p = (BlockPos)args[0];
          return naturalBiomes.manager.getBiome(
              new BlockPos(sourceX + p.getX() - originX, p.getY(),
                           sourceZ + p.getZ() - originZ));
        }
        return level.registryAccess()
            .registryOrThrow(Registries.BIOME)
            .getHolderOrThrow(Biomes.SWAMP);
      case "getHeight": {
        Heightmap.Types type = (Heightmap.Types)args[0];
        return height(type, (int)args[1], (int)args[2]);
      }
      case "getHeightmapPos": {
        BlockPos p = (BlockPos)args[1];
        return new BlockPos(
            p.getX(), height((Heightmap.Types)args[0], p.getX(), p.getZ()),
            p.getZ());
      }
      case "getMinBuildHeight":
        return -64;
      case "getMaxBuildHeight":
        return 320;
      case "getHeightAccessorForGeneration":
        return LevelHeightAccessor.create(-64, 384);
      case "getSeaLevel":
        return 63;
      case "getLevel":
        return level;
      case "getRandom":
        return random;
      case "getChunk":
        return chunk;
      case "getBlockEntity":
        return null; // Inventory contents do not affect block placement/height.
      case "scheduleTick":
        return null; // No fluid/gameplay ticks during structure generation.
      case "addFreshEntity":
        return false; // Entities do not enter heightmap computation.
      case "isEmptyBlock":
        return block((BlockPos)args[0]).isAir();
      case "isOutsideBuildHeight": {
        int y = args[0] instanceof BlockPos ? ((BlockPos)args[0]).getY()
                                            : (int)args[0];
        return y < -64 || y >= 320;
      }
      case "isClientSide":
        return false;
      case "toString":
        return "ControlledRoomTerrain";
      case "hashCode":
        return System.identityHashCode(proxy);
      case "equals":
        return proxy == args[0];
      default:
        throw new UnsupportedOperationException("Unmodeled world access: " +
                                                method);
      }
    }
  }
  public static JsonObject run(Object serverObject, JsonObject input)
      throws Exception {
    MinecraftServer server = (MinecraftServer)serverObject;
    JsonObject model = input.getAsJsonObject("controlled_model");
    Terrain terrain = new Terrain(server.overworld(), model);
    int ox = terrain.originX, oz = terrain.originZ;
    WorldGenLevel world = (WorldGenLevel)Proxy.newProxyInstance(
        LayoutPlacementReplay.class.getClassLoader(),
        new Class<?>[] {WorldGenLevel.class}, terrain);
    long target = Long.parseLong(model.get("mine_target").getAsString());
    WorldgenRandom layoutRandom = new WorldgenRandom(new LegacyRandomSource(0));
    layoutRandom.setLargeFeatureSeed(target, 0, 0);
    layoutRandom.nextDouble();
    MineshaftPieces.MineShaftRoom room = new MineshaftPieces.MineShaftRoom(
        0, layoutRandom, ox + 2, oz + 2, MineshaftStructure.Type.NORMAL);
    StructurePiecesBuilder builder = new StructurePiecesBuilder();
    builder.addPiece(room);
    room.addChildren(room, builder, layoutRandom);
    builder.moveBelowSeaLevel(63, -64, layoutRandom, 10);
    int actualRoomBottom = room.getBoundingBox().minY();
    boolean startAllowed =
        terrain.naturalBiomes == null ||
        terrain.naturalBiomes.permitsMineshaft(
            terrain.sourceX + 8, actualRoomBottom, terrain.sourceZ);

    BoundingBox clip = new BoundingBox(ox, -64, oz, ox + 15, 319, oz + 15);

    boolean roomVeto = false;
    for (StructurePiece piece : builder.build().pieces()) {
      if (!startAllowed || !piece.getBoundingBox().intersects(clip))
        continue;
      if (piece == room)
        roomVeto = (Boolean)VanillaQueryMain.invokeMethod(
            piece, "isInInvalidLocation", world, clip);
      piece.postProcess(world, null, null, terrain.random, clip,
                        new ChunkPos(ox >> 4, oz >> 4),
                        new BlockPos(ox, 0, oz));
    }

    WorldgenRandom hutRandom = new WorldgenRandom(new LegacyRandomSource(0));
    hutRandom.setLargeFeatureSeed(target, 0, 0);
    SwampHutPiece hut = new SwampHutPiece(hutRandom, ox, oz);
    if (hut.getBoundingBox().getXSpan() != terrain.hutWidth) {
      for (int orientationSeed = 0; orientationSeed < 1000; orientationSeed++) {
        SwampHutPiece candidate =
            new SwampHutPiece(new LegacyRandomSource(orientationSeed), ox, oz);
        if (candidate.getBoundingBox().getXSpan() == terrain.hutWidth) {
          hut = candidate;
          break;
        }
      }
    }
    if (hut.getBoundingBox().getXSpan() != terrain.hutWidth ||
        hut.getBoundingBox().getZSpan() != 63 / terrain.hutWidth ||
        hut.getBoundingBox().minX() != ox || hut.getBoundingBox().minZ() != oz)
      throw new IllegalStateException("orientation mismatch");
    VanillaQueryMain.invokeMethod(hut, "updateAverageGroundHeight", world, clip,
                                  0);
    int height = (int)VanillaQueryMain.readField(hut, "heightPosition");
    JsonObject result = new JsonObject();
    result.addProperty("actual_room_bottom", actualRoomBottom);
    result.addProperty("layout_pieces", builder.build().pieces().size());
    result.addProperty("mineshaft_start_allowed", startAllowed);
    result.addProperty("natural_biomes", terrain.naturalBiomes != null);
    JsonArray heights = new JsonArray();
    heights.add(height);
    result.add("heights", heights);
    JsonArray roomBox = new JsonArray();
    BoundingBox roomBounds = room.getBoundingBox();
    for (int value :
         new int[] {roomBounds.minX(), roomBounds.minY(), roomBounds.minZ(),
                    roomBounds.maxX(), roomBounds.maxY(), roomBounds.maxZ()})
      roomBox.add(value);
    result.add("room_box", roomBox);
    result.addProperty("room_veto", roomVeto);
    return result;
  }
}
