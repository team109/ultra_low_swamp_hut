"""Compile-time seams for the vanilla FEATURES prefix executor."""

import re


def adapt_enumerator_source(source, version):
    parts = tuple(map(int, version.split('.')))
    if parts < (1, 21):
        source = source.replace('import net.minecraft.util.StaticCache2D;', '').replace('import net.minecraft.world.level.chunk.status.*;', '')
        start = source.index(' static final class Holder extends GenerationChunkHolder {')
        end = source.index('\n record Snapshot', start)
        source = source[:start] + ''' static final class Holder {
  ProtoChunk chunk;
  Holder(ProtoChunk chunk){this.chunk=chunk;}
  void set(ProtoChunk chunk){this.chunk=chunk;}
 }
''' + source[end:]
        source = source.replace('static WorldGenContext context;', 'static Object context;')
        source = source.replace('static ChunkStep FEATURES;', 'static Object FEATURES;')
        start = source.index(' static StaticCache2D<GenerationChunkHolder> cache(')
        end = source.index('\n record Checkpoint', start)
        source = source[:start] + ''' static Map<Long,Holder> cache(Map<Long,Holder> holders){return holders;}
 static void decorate(Map<Long,Holder> holders,Map<Long,Holder> cache,int x,int z)throws Exception {
  if(!OBSERVE)VersionQueryObservation.reset(Integer.MIN_VALUE,Integer.MIN_VALUE);
  int before=VersionQueryObservation.featureOrder().size();
  var nearby=new ArrayList<ChunkAccess>();
  for(int dz=-8;dz<=8;dz++)for(int dx=-8;dx<=8;dx++)nearby.add(holders.get(ChunkPos.asLong(x+dx,z+dz)).chunk);
  var source=level.getChunkSource();
  var future=ChunkStatus.FEATURES.generate(Runnable::run,level,source.getGenerator(),level.getStructureManager(),source.getLightEngine(),chunk->CompletableFuture.completedFuture(com.mojang.datafixers.util.Either.left(chunk)),nearby,false);
  VanillaQueryMain.server.await(future);VanillaQueryMain.server.drain();
  var observed=VersionQueryObservation.featureOrder();
  if(observed.size()!=before+1)throw new IllegalStateException("Expected exactly one FEATURES step");
  var actual=observed.get(before).getAsJsonArray();if(actual.get(0).getAsInt()!=x||actual.get(1).getAsInt()!=z)throw new IllegalStateException("Unexpected FEATURES center "+actual);
 }
''' + source[end:]
        source = source.replace('StaticCache2D<GenerationChunkHolder> cache', 'Map<Long,Holder> cache')
        source = source.replace('FEATURES=ChunkPyramid.GENERATION_PYRAMID.getStepTo(ChunkStatus.FEATURES);', '')
        if parts < (1, 20, 5):
            source = source.replace('context=(WorldGenContext)VanillaQueryMain.readField(source.chunkMap,"worldGenContext");', '')
        source = source.replace('if(!((ChunkResult<?>)future.join()).isSuccess())', 'if(((com.mojang.datafixers.util.Either<?,?>)future.join()).left().isEmpty())')
        source = source.replace('chunk.getPersistedStatus()', 'chunk.getStatus()').replace('chunk.setPersistedStatus(', 'chunk.setStatus(')
        source = source.replace('var holder=(GenerationChunkHolder)', 'var holder=(ChunkHolder)').replace('holder.getLatestChunk()', 'holder.getLastAvailable()')
        source = re.sub(r'   @SuppressWarnings\("unchecked"\)var futures=.*?\n   var featureFuture=.*?\n', '', source)
        source = source.replace('chunk.getStatus().isBefore(ChunkStatus.CARVERS)', '!chunk.getStatus().isOrAfter(ChunkStatus.CARVERS)')
    if parts < (1, 20, 5):
        source = source.replace('entity.saveWithFullMetadata(level.registryAccess())', 'entity.saveWithFullMetadata()')
        source = source.replace('tag,level.registryAccess());', 'tag);')
    if parts < (1, 21):
        source = source.replace('net.minecraft.resources.ResourceLocation.parse("minecraft:swamp_hut")', 'new net.minecraft.resources.ResourceLocation("minecraft:swamp_hut")')
    if (1, 20) <= parts < (1, 20, 5):
        source = source.replace('nearby,false);', 'nearby);')
    if parts < (1, 20):
        source = source.replace('   ProtoChunk chunk=holder.chunk;', """   ProtoChunk chunk=holder.chunk;
   @SuppressWarnings("unchecked")var lights=(List<Object>)VanillaQueryMain.readField(chunk,"lights");
   var savedLights=new ArrayList<Object>(lights);undo.add(()->{lights.clear();lights.addAll(savedLights);});
   Object lightEngine=VanillaQueryMain.readField(chunk,"lightEngine");undo.add(()->VanillaQueryMain.writeField(chunk,"lightEngine",lightEngine));""")
        source = source.replace('ChunkStatus.CARVERS,true', 'ChunkStatus.LIQUID_CARVERS,true')
    if parts < (1, 21):
        source = source.replace('new RegionStorageInfo("enumeration-memory",Level.OVERWORLD,"chunk"),', '')
    if (1, 20, 6) <= parts < (1, 21):
        source = source.replace('import net.minecraft.world.level.chunk.storage.*;', 'import net.minecraft.world.level.chunk.storage.*;\nimport net.minecraft.world.level.chunk.status.*;')
        source = source.replace('static Object context;', 'static WorldGenContext context;')
        source = source.replace('var source=level.getChunkSource();\n  var future=ChunkStatus.FEATURES.generate(Runnable::run,level,source.getGenerator(),level.getStructureManager(),source.getLightEngine(),chunk->CompletableFuture.completedFuture(com.mojang.datafixers.util.Either.left(chunk)),nearby,false);', 'var source=level.getChunkSource();\n  var future=ChunkStatus.FEATURES.generate(context,Runnable::run,(chunk)->CompletableFuture.completedFuture(chunk),nearby);')
        source = source.replace('if(((com.mojang.datafixers.util.Either<?,?>)future.join()).left().isEmpty())', 'if(!((ChunkResult<?>)future.join()).isSuccess())')
    if parts >= (1, 21, 2):
        source = source.replace('public int getTicketLevel(){return 33;}', 'public void addSaveDependency(CompletableFuture<?> future){}\n  public int getTicketLevel(){return 33;}')
        source = source.replace('registry.get(net.minecraft.resources.ResourceLocation.parse("minecraft:swamp_hut"))', 'registry.getValue(net.minecraft.resources.ResourceLocation.parse("minecraft:swamp_hut"))')
        source = source.replace('ChunkSerializer.write(level,e.getValue().chunk)', 'SerializableChunkData.copyOf(level,e.getValue().chunk).write()')
        source = source.replace('ChunkSerializer.read(level,level.getPoiManager(),new RegionStorageInfo("enumeration-memory",Level.OVERWORLD,"chunk"),pos,tag.copy())', 'SerializableChunkData.parse(level,level.registryAccess(),tag.copy()).read(level,level.getPoiManager(),new RegionStorageInfo("enumeration-memory",Level.OVERWORLD,"chunk"),pos)')
        source = source.replace('.registryOrThrow(', '.lookupOrThrow(')
    if parts >= (1, 21, 5):
        source = re.sub(r'\.getCompound\(([^()]*)\)', r'.getCompoundOrEmpty(\1)', source)
        source = re.sub(r'\.getLongArray\((registry.getKey\(entry.getKey\(\)\).toString\(\)|[^()]*)\)', r'.getLongArray(\1).orElseThrow()', source)
        source = source.replace('heightmaps.getAllKeys()', 'heightmaps.keySet()')
    if parts >= (26, 1):
        source = source.replace('ChunkPos.asLong(', 'ChunkPos.pack(')
        source = source.replace('new ChunkPos(e.getKey())', 'ChunkPos.unpack(e.getKey())')
        source = source.replace('SerializableChunkData.parse(level,level.registryAccess(),', 'SerializableChunkData.parse(level,PalettedContainerFactory.create(level.registryAccess()),')
        source = source.replace('net.minecraft.resources.ResourceLocation', 'net.minecraft.resources.Identifier')
    if parts >= (1, 21, 6):
        source = source.replace('net.minecraft.SharedConstants.getCurrentVersion().getId()', 'System.getProperty("hut.service.version")')
    if parts >= (1, 21, 11):
        source = source.replace('net.minecraft.resources.ResourceLocation', 'net.minecraft.resources.Identifier')
    if parts >= (1, 21, 9):
        source = source.replace('SerializableChunkData.parse(level,level.registryAccess(),', 'SerializableChunkData.parse(level,PalettedContainerFactory.create(level.registryAccess()),')
        start = source.index('  Object data=VanillaQueryMain.readField(original,"data");')
        end = source.index('\n }', start)
        source = source[:start] + '  return original.copy();' + source[end:]
        source = source.replace('net.minecraft.SharedConstants.getCurrentVersion().getId()', 'System.getProperty("hut.service.version")')
    if parts >= (26, 3):
        source = source.replace('ChunkStatus.CARVERS', 'ChunkStatus.TERRAIN')
    return source
