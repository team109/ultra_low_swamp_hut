import java.util.*;
import net.minecraft.core.*;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.biome.*;
import net.minecraft.world.level.dimension.LevelStem;
import net.minecraft.world.level.levelgen.*;

/**
 * Vanilla biome queries for a captured terrain's original seed and
 * coordinates.
 */
final class NaturalBiomeSampler {
  private static final Map<Long, NaturalBiomeSampler> cache =
      new LinkedHashMap<Long, NaturalBiomeSampler>(32, .75f, true) {
        protected boolean removeEldestEntry(
            Map.Entry<Long, NaturalBiomeSampler> entry) {
          return size() > 32;
        }
      };
  final BiomeManager manager;
  final BiomeManager.NoiseBiomeSource noiseBiomes;
  final HolderSet<Biome> mineshaftBiomes;

  private NaturalBiomeSampler(ServerLevel level, long seed) {
    var generator = (NoiseBasedChunkGenerator)level.registryAccess()
                        .registryOrThrow(Registries.LEVEL_STEM)
                        .getOrThrow(LevelStem.OVERWORLD)
                        .generator();
    var state = RandomState.create(
        generator.generatorSettings().value(),
        level.registryAccess().registryOrThrow(Registries.NOISE).asLookup(),
        seed);
    Map<BlockPos, Holder<Biome>> samples = new HashMap<>();
    noiseBiomes = (x, y, z)
        -> samples.computeIfAbsent(
            new BlockPos(x, y, z),
            p
            -> generator.getBiomeSource().getNoiseBiome(
                p.getX(), p.getY(), p.getZ(), state.sampler()));
    manager = new BiomeManager(noiseBiomes, BiomeManager.obfuscateSeed(seed));
    mineshaftBiomes = level.registryAccess()
                          .registryOrThrow(Registries.STRUCTURE)
                          .get(ResourceLocation.parse("minecraft:mineshaft"))
                          .biomes();
  }

  static NaturalBiomeSampler get(ServerLevel level, long seed) {
    return cache.computeIfAbsent(seed, s -> new NaturalBiomeSampler(level, s));
  }

  boolean permitsMineshaft(int x, int y, int z) {
    return mineshaftBiomes.contains(noiseBiomes.getNoiseBiome(
        QuartPos.fromBlock(x), QuartPos.fromBlock(y), QuartPos.fromBlock(z)));
  }
}
