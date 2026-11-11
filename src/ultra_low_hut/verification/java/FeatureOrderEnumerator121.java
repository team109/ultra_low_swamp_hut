import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import com.google.gson.*;
import net.minecraft.server.level.*;
import net.minecraft.util.StaticCache2D;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.level.*;
import net.minecraft.world.level.chunk.*;
import net.minecraft.world.level.chunk.status.*;
import net.minecraft.world.level.chunk.storage.*;

/** Resident vanilla FEATURES executor for the selected center-ending prefix trie.
 * CARVERS terrain is shared across a case; neighbor edges use transactional undo.
 * Usage: --serve, with one JSON query and response per line.
 */
public final class FeatureOrderEnumerator121 {
 static final class Holder extends GenerationChunkHolder {
  ProtoChunk chunk;
  Holder(ProtoChunk chunk)throws Exception {
   super(chunk.getPos());set(chunk);
  }
  void set(ProtoChunk chunk)throws Exception {
   this.chunk=chunk;
   @SuppressWarnings("unchecked") var fs=(AtomicReferenceArray<CompletableFuture<ChunkResult<ChunkAccess>>>)VanillaQueryMain.readField(this,"futures");
   for(ChunkStatus status:ChunkStatus.getStatusList())fs.set(status.getIndex(),status.isOrBefore(chunk.getPersistedStatus())?CompletableFuture.completedFuture(ChunkResult.of(chunk)):null);
  }
  public int getTicketLevel(){return 33;}
  public int getQueueLevel(){return 33;}
 }
 record Snapshot(Map<Long,CompoundTag> chunks){}
 static int cx,cz;static ServerLevel level;static WorldGenContext context;
 static ChunkStep FEATURES;static boolean OBSERVE=true;
 static Snapshot snapshot(Map<Long,Holder> holders){
  var tags=new LinkedHashMap<Long,CompoundTag>();for(var e:holders.entrySet()){
   CompoundTag tag=ChunkSerializer.write(level,e.getValue().chunk).copy(),heightmaps=new CompoundTag();
   for(var height:e.getValue().chunk.getHeightmaps())heightmaps.putLongArray(height.getKey().name(),height.getValue().getRawData().clone());tag.put("__all_heightmaps",heightmaps);tags.put(e.getKey(),tag);
  }return new Snapshot(tags);
 }
 static ProtoChunk read(ChunkPos pos,CompoundTag tag)throws Exception {
  ProtoChunk chunk=ChunkSerializer.read(level,level.getPoiManager(),new RegionStorageInfo("enumeration-memory",Level.OVERWORLD,"chunk"),pos,tag.copy());
  // Vanilla's loader rebuilds LongOpenHashSet with a different capacity, which
  // can reorder starts sharing the decoration RNG. The saved long-array order
  // is therefore generation state, even though set membership is unchanged.
  CompoundTag references=tag.getCompound("structures").getCompound("References");
  var registry=level.registryAccess().registryOrThrow(net.minecraft.core.registries.Registries.STRUCTURE);
  var ordered=new LinkedHashMap<net.minecraft.world.level.levelgen.structure.Structure,it.unimi.dsi.fastutil.longs.LongSet>();
  for(var entry:chunk.getAllReferences().entrySet()){
   long[] saved=references.getLongArray(registry.getKey(entry.getKey()).toString());
   var set=new it.unimi.dsi.fastutil.longs.LongLinkedOpenHashSet(saved);
   if(!Arrays.equals(saved,set.toLongArray()))throw new IllegalStateException("Structure-reference iteration order was not restored");
   ordered.put(entry.getKey(),set);
  }
  chunk.setAllReferences(ordered);
  ((Map<?,?>)VanillaQueryMain.readField(chunk,"heightmaps")).clear();CompoundTag heightmaps=tag.getCompound("__all_heightmaps");
  for(String name:heightmaps.getAllKeys())chunk.setHeightmap(net.minecraft.world.level.levelgen.Heightmap.Types.valueOf(name),heightmaps.getLongArray(name).clone());
  return chunk;
 }
 static StaticCache2D<GenerationChunkHolder> cache(Map<Long,Holder> holders){
  return StaticCache2D.create(cx,cz,9,(x,z)->{var h=holders.get(ChunkPos.asLong(x,z));if(h==null)throw new IllegalStateException("Missing "+x+","+z);return h;});
 }
 static void decorate(Map<Long,Holder> holders,StaticCache2D<GenerationChunkHolder> cache,int x,int z)throws Exception {
  if(!OBSERVE)VersionQueryObservation.reset(Integer.MIN_VALUE,Integer.MIN_VALUE);
  int observedBefore=VersionQueryObservation.featureOrder().size();
  Holder holder=holders.get(ChunkPos.asLong(x,z));FEATURES.apply(context,cache,holder.chunk).join();VanillaQueryMain.server.drain();
  JsonArray observed=VersionQueryObservation.featureOrder();
  if(observed.size()!=observedBefore+1)throw new IllegalStateException("Expected exactly one actual FEATURES step");
  JsonArray actual=observed.get(observedBefore).getAsJsonArray();if(actual.size()!=2||actual.get(0).getAsInt()!=x||actual.get(1).getAsInt()!=z)throw new IllegalStateException("Unexpected actual FEATURES center: "+actual);
  @SuppressWarnings("unchecked")var fs=(AtomicReferenceArray<CompletableFuture<ChunkResult<ChunkAccess>>>)VanillaQueryMain.readField(holder,"futures");
  fs.set(ChunkStatus.FEATURES.getIndex(),CompletableFuture.completedFuture(ChunkResult.of(holder.chunk)));
 }
 record Checkpoint(Snapshot chunks,Map<Long,Map<net.minecraft.world.level.levelgen.structure.Structure,net.minecraft.world.level.levelgen.structure.StructureStart>> starts,StructureGraphSnapshot121 graph,StateKey audit){}
 static Checkpoint checkpoint(Map<Long,Holder> holders,int x,int z)throws Exception {
  var nearby=new LinkedHashMap<Long,Holder>();for(int dz=-1;dz<=1;dz++)for(int dx=-1;dx<=1;dx++){long key=ChunkPos.asLong(x+dx,z+dz);nearby.put(key,holders.get(key));}
  var starts=new LinkedHashMap<Long,Map<net.minecraft.world.level.levelgen.structure.Structure,net.minecraft.world.level.levelgen.structure.StructureStart>>();var roots=new ArrayList<Object>();
  for(var e:holders.entrySet())if(!e.getValue().chunk.getAllStarts().isEmpty()){
   var copy=new LinkedHashMap<>(e.getValue().chunk.getAllStarts());starts.put(e.getKey(),copy);roots.addAll(copy.values());
  }
  return new Checkpoint(snapshot(nearby),starts,new StructureGraphSnapshot121(roots),Boolean.getBoolean("hut.enumeration.auditUndo")?stateKey(holders,0):null);
 }
 static void rollback(Map<Long,Holder> holders,Checkpoint checkpoint)throws Exception {
  checkpoint.graph.restore();
  for(var e:checkpoint.chunks.chunks.entrySet()){
   ChunkPos pos=new ChunkPos(e.getKey());CompoundTag tag=e.getValue().copy();tag.getCompound("structures").put("starts",new CompoundTag());holders.get(e.getKey()).set(read(pos,tag));
  }
  for(var e:checkpoint.starts.entrySet())holders.get(e.getKey()).chunk.setAllStarts(e.getValue());
  if(checkpoint.audit!=null&&!checkpoint.audit.equals(stateKey(holders,0)))throw new IllegalStateException("Per-step rollback full state differs");
 }
 /** In-memory undo: copy mutable palettes once on entry, restore original references.
  * FEATURES mutates section palettes, heightmaps, ticks, entity lists and maps;
  * CARVERS noise, biome palettes and carving masks remain read-only. */
 @SuppressWarnings("unchecked")
 static <T> PalettedContainer<T> copyStates(PalettedContainer<T> original)throws Exception {
  Object data=VanillaQueryMain.readField(original,"data");
  var palette=(Palette<T>)VanillaQueryMain.readField(data,"palette");var entries=new ArrayList<T>();for(int i=0;i<palette.getSize();i++)entries.add(palette.valueFor(i));
  var storage=(net.minecraft.util.BitStorage)VanillaQueryMain.readField(data,"storage");
  return (PalettedContainer<T>)VanillaQueryMain.construct(PalettedContainer.class,VanillaQueryMain.readField(original,"registry"),VanillaQueryMain.readField(original,"strategy"),VanillaQueryMain.readField(data,"configuration"),storage.copy(),entries);
 }
 static final java.lang.reflect.Field[] SECTION_FIELDS=sectionFields();
 static final java.lang.reflect.Field SECTION_STATES=sectionStates();
 static java.lang.reflect.Field[] sectionFields(){var fields=new ArrayList<java.lang.reflect.Field>();for(var field:LevelChunkSection.class.getDeclaredFields())if(!java.lang.reflect.Modifier.isStatic(field.getModifiers())){field.setAccessible(true);fields.add(field);}return fields.toArray(java.lang.reflect.Field[]::new);}
 static java.lang.reflect.Field sectionStates(){try{return VanillaQueryMain.findField(LevelChunkSection.class,"states");}catch(Exception e){throw new ExceptionInInitializerError(e);}}
 static final Deque<MemoryCheckpoint> MEMORY_FRAMES=new ArrayDeque<>();
 static java.lang.reflect.Field sectionObserverField;
 static java.util.function.Consumer<Object> sectionObserver;
 static boolean installSectionObserver(){
  if(Boolean.getBoolean("hut.prefix.eagerSections"))return false;
  try{sectionObserverField=VersionQueryRuntime.class.getField("sectionWriteObserver");sectionObserver=(section)->{try{if(!MEMORY_FRAMES.isEmpty())MEMORY_FRAMES.peek().captureSection((LevelChunkSection)section);}catch(Exception e){throw new IllegalStateException(e);}};return true;}
  catch(NoSuchFieldException absent){return false;}catch(Exception e){throw new IllegalStateException(e);}
 }
 static boolean sectionCow;
 static final boolean SKIP_POST_HUT_FEATURES=Boolean.getBoolean("hut.prefix.skipPostHutFeatures");
 static java.lang.reflect.Field centerProbeActiveField,centerHeightReadyField,centerTargetPieceField;
 static void initializeCenterProbe()throws Exception {if(SKIP_POST_HUT_FEATURES){centerProbeActiveField=VersionQueryRuntime.class.getField("centerProbeActive");centerHeightReadyField=VersionQueryRuntime.class.getField("centerHeightReady");centerTargetPieceField=VersionQueryRuntime.class.getField("centerTargetPiece");}}
 static void centerProbe(boolean active,Object piece)throws Exception {if(SKIP_POST_HUT_FEATURES){centerHeightReadyField.setBoolean(null,false);centerTargetPieceField.set(null,active?piece:null);centerProbeActiveField.setBoolean(null,active);}}
 static final class MemoryCheckpoint {
  final List<RunnableUndo> undo=new ArrayList<>();
  final StructureGraphSnapshot121 graph;
  final Set<LevelChunkSection> copiedSections=Collections.newSetFromMap(new IdentityHashMap<>());
  void captureSection(LevelChunkSection section)throws Exception {
   if(!copiedSections.add(section))return;Object[] values=new Object[SECTION_FIELDS.length];for(int i=0;i<values.length;i++)values[i]=SECTION_FIELDS[i].get(section);
   undo.add(()->{for(int i=0;i<values.length;i++)SECTION_FIELDS[i].set(section,values[i]);});
   SECTION_STATES.set(section,copyStates(section.getStates()));
  }
  MemoryCheckpoint(Map<Long,Holder> holders,int x,int z)throws Exception {this(holders,x,z,1);}
  MemoryCheckpoint(Map<Long,Holder> holders,int x,int z,int radius)throws Exception {
   var roots=new ArrayList<Object>();
   if(Boolean.getBoolean("hut.prefix.allStructureRoots"))for(var h:holders.values())roots.addAll(h.chunk.getAllStarts().values());
   else {
    // Decoration visits only starts referenced by this FEATURES chunk.
    // Independent queries save the union of the 3x3 query targets.
    int targets=radius==2?1:0;
    for(int dz=-targets;dz<=targets;dz++)for(int dx=-targets;dx<=targets;dx++){
     ProtoChunk target=holders.get(ChunkPos.asLong(x+dx,z+dz)).chunk;roots.addAll(target.getAllStarts().values());
     for(var references:target.getAllReferences().entrySet())for(long position:references.getValue()){
      Holder origin=holders.get(position);if(origin==null)throw new IllegalStateException("Missing structure-reference origin");
      Object start=origin.chunk.getAllStarts().get(references.getKey());if(start!=null)roots.add(start);
     }
    }
   }
   graph=new StructureGraphSnapshot121(roots);
   for(int dz=-radius;dz<=radius;dz++)for(int dx=-radius;dx<=radius;dx++)capture(holders.get(ChunkPos.asLong(x+dx,z+dz)));
   if(sectionCow){if(MEMORY_FRAMES.isEmpty())sectionObserverField.set(null,sectionObserver);MEMORY_FRAMES.push(this);}
  }
  void capture(Holder holder)throws Exception {
   ProtoChunk chunk=holder.chunk;
   LevelChunkSection[] sections=chunk.getSections(),original=sections.clone();
   if(!sectionCow)for(int i=0;i<sections.length;i++){
    LevelChunkSection old=sections[i];
    var copy=VanillaQueryMain.allocateWithoutConstructor(LevelChunkSection.class);
    for(var field:SECTION_FIELDS)field.set(copy,field.get(old));
    SECTION_STATES.set(copy,copyStates(old.getStates()));
    sections[i]=copy;
   }
   undo.add(()->System.arraycopy(original,0,sections,0,sections.length));
   @SuppressWarnings("unchecked")var heightmaps=(Map<net.minecraft.world.level.levelgen.Heightmap.Types,net.minecraft.world.level.levelgen.Heightmap>)VanillaQueryMain.readField(chunk,"heightmaps");
   var savedHeightmaps=new EnumMap<net.minecraft.world.level.levelgen.Heightmap.Types,long[]>(net.minecraft.world.level.levelgen.Heightmap.Types.class);
   for(var entry:heightmaps.entrySet())savedHeightmaps.put(entry.getKey(),entry.getValue().getRawData().clone());
   undo.add(()->{heightmaps.keySet().retainAll(savedHeightmaps.keySet());for(var e:savedHeightmaps.entrySet())chunk.setHeightmap(e.getKey(),e.getValue());});
   Object[] post=(Object[])VanillaQueryMain.readField(chunk,"postProcessing"),savedPost=post.clone();
   for(int i=0;i<post.length;i++)if(post[i]!=null)post[i]=new it.unimi.dsi.fastutil.shorts.ShortArrayList((it.unimi.dsi.fastutil.shorts.ShortList)post[i]);
   undo.add(()->System.arraycopy(savedPost,0,post,0,post.length));
   for(String name:List.of("pendingBlockEntities","blockEntities")){
    @SuppressWarnings("unchecked")Map<Object,Object> map=(Map<Object,Object>)VanillaQueryMain.readField(chunk,name);
    var saved=new LinkedHashMap<Object,Object>();
    for(var e:map.entrySet()){
     Object value=e.getValue();
     if(value instanceof CompoundTag tag)value=tag.copy();
     else if(value instanceof net.minecraft.world.level.block.entity.BlockEntity entity){
      CompoundTag tag=entity.saveWithFullMetadata(level.registryAccess());
      value=net.minecraft.world.level.block.entity.BlockEntity.loadStatic(entity.getBlockPos(),entity.getBlockState(),tag,level.registryAccess());
     }
     saved.put(e.getKey(),value);
    }
    undo.add(()->{map.clear();map.putAll(saved);});
   }
   @SuppressWarnings("unchecked")List<CompoundTag> entities=(List<CompoundTag>)VanillaQueryMain.readField(chunk,"entities");
   var savedEntities=new ArrayList<CompoundTag>();for(var entity:entities)savedEntities.add(entity.copy());
   undo.add(()->{entities.clear();entities.addAll(savedEntities);});
   for(String tickName:List.of("blockTicks","fluidTicks")){
    Object tick=VanillaQueryMain.readField(chunk,tickName);
    for(String name:List.of("ticks","ticksPerPosition")){
     @SuppressWarnings("unchecked")Collection<Object> values=(Collection<Object>)VanillaQueryMain.readField(tick,name);var saved=new ArrayList<>(values);
     undo.add(()->{values.clear();values.addAll(saved);});
    }
   }
   for(String name:List.of("status","unsaved","isLightCorrect","inhabitedTime")){
    var field=VanillaQueryMain.findField(chunk.getClass(),name);Object value=field.get(chunk);undo.add(()->field.set(chunk,value));
   }
   @SuppressWarnings("unchecked")var futures=(AtomicReferenceArray<CompletableFuture<ChunkResult<ChunkAccess>>>)VanillaQueryMain.readField(holder,"futures");
   var featureFuture=futures.get(ChunkStatus.FEATURES.getIndex());undo.add(()->futures.set(ChunkStatus.FEATURES.getIndex(),featureFuture));
  }
  void restore()throws Exception {if(sectionCow&&MEMORY_FRAMES.peek()!=this)throw new IllegalStateException("Non-LIFO memory undo");graph.restore();for(int i=undo.size()-1;i>=0;i--)undo.get(i).run();if(sectionCow){MEMORY_FRAMES.pop();if(MEMORY_FRAMES.isEmpty())sectionObserverField.set(null,null);}}
 }
 interface RunnableUndo {void run()throws Exception;}
 static Object sparseCheckpoint(Map<Long,Holder> holders,int index)throws Exception {
  int x=cx+(index==8?0:NEIGHBORS[index][0]),z=cz+(index==8?0:NEIGHBORS[index][1]);
  return Boolean.getBoolean("hut.prefix.nbtUndo")?checkpoint(holders,x,z):new MemoryCheckpoint(holders,x,z);
 }
 static void sparseRollback(Map<Long,Holder> holders,Object value)throws Exception {
  if(value instanceof MemoryCheckpoint checkpoint)checkpoint.restore();else rollback(holders,(Checkpoint)value);
 }
 record StateKey(int used,Snapshot chunks,List<Object> structures){}
 // Canonicalize only inspection order, without changing the live start map.
 // Reference LongSet iteration order remains significant and is preserved.
 static List<Object> orderedStructureRoots(Map<Long,Holder> holders){
  var positions=new ArrayList<>(holders.keySet());
  positions.sort(Comparator.comparingInt((Long key)->ChunkPos.getX(key)).thenComparingInt(key->ChunkPos.getZ(key)));
  var registry=level.registryAccess().registryOrThrow(net.minecraft.core.registries.Registries.STRUCTURE);
  var roots=new ArrayList<Object>();
  for(long key:positions){
   var entries=new ArrayList<>(holders.get(key).chunk.getAllStarts().entrySet());
   entries.sort(Comparator.comparing(entry->registry.getKey(entry.getKey()).toString()));
   for(var entry:entries)roots.add(entry.getValue());
  }
  return roots;
 }
 static StateKey stateKey(Map<Long,Holder> holders,int used)throws Exception {
  var nearby=new LinkedHashMap<Long,Holder>();for(int dz=-2;dz<=2;dz++)for(int dx=-2;dx<=2;dx++){long key=ChunkPos.asLong(cx+dx,cz+dz);nearby.put(key,holders.get(key));}
  return new StateKey(used,snapshot(nearby),new StructureGraphSnapshot121(orderedStructureRoots(holders)).key());
 }
 static final int[][] NEIGHBORS={{0,-1},{1,-1},{1,0},{1,1},{0,1},{-1,1},{-1,0},{-1,-1}};
 static final Gson NULL_JSON=new GsonBuilder().serializeNulls().create();
 // Structure starts are complete before CARVERS. FEATURES places existing
 // pieces; it cannot create a missing swamp-hut start in this vanilla model.
 static JsonObject absenceProof(Map<Long,Holder> holders){
  var chunk=holders.get(ChunkPos.asLong(cx,cz)).chunk;
  if(chunk.getPersistedStatus().isBefore(ChunkStatus.CARVERS))throw new IllegalStateException("Incomplete target start map");
  int huts=0;for(var start:chunk.getAllStarts().values())if(start.isValid())for(var piece:start.getPieces())if(piece instanceof net.minecraft.world.level.levelgen.structure.structures.SwampHutPiece)huts++;
  if(huts!=0)return null;
  var registry=level.registryAccess().registryOrThrow(net.minecraft.core.registries.Registries.STRUCTURE);
  var hut=registry.get(net.minecraft.resources.ResourceLocation.parse("minecraft:swamp_hut"));
  if(!(hut instanceof net.minecraft.world.level.levelgen.structure.structures.SwampHutStructure))throw new IllegalStateException("Missing vanilla swamp-hut registry entry");
  boolean present=chunk.getAllStarts().containsKey(hut);var start=chunk.getAllStarts().get(hut);
  if(present&&start!=net.minecraft.world.level.levelgen.structure.StructureStart.INVALID_START)throw new IllegalStateException("Unexpected swamp-hut start without its target piece");
  if(VersionQueryObservation.featureOrder().size()!=0)throw new IllegalStateException("Absence proof requires a pre-FEATURES start map");
  var proof=new JsonObject();proof.addProperty("stage","CARVERS");proof.addProperty("structure_start_map_complete",true);proof.addProperty("target_hut_piece_count",0);proof.addProperty("swamp_hut_start_present",present);proof.addProperty("swamp_hut_start_valid",false);proof.addProperty("swamp_hut_start_invalid_placeholder",present);proof.addProperty("features_creates_structure_starts",false);return proof;
 }
 static Map<Long,Holder> prepareSparse(long seed,int x,int z,VanillaQueryMain.WorldConfiguration world)throws Exception {
  cx=Math.floorDiv(x,16);cz=Math.floorDiv(z,16);
  if(VanillaQueryMain.server==null)VanillaQueryMain.server=VanillaQueryMain.createWorldContext(seed,world.biome(),world.worldType());
  else VanillaQueryMain.resetGenerationContext(seed,world.biome(),world.worldType());
  VanillaQueryMain.contextSeed=seed;VanillaQueryMain.contextBiome=world.biome();VanillaQueryMain.contextWorldType=world.worldType();VanillaQueryMain.contextMode="features";level=VanillaQueryMain.server.overworld();
  FEATURES=ChunkPyramid.GENERATION_PYRAMID.getStepTo(ChunkStatus.FEATURES);var source=level.getChunkSource();
  for(int dz=-2;dz<=2;dz++)for(int dx=-2;dx<=2;dx++){
   var future=(CompletableFuture<?>)VanillaQueryMain.invokeMethod(source,"getChunkFutureMainThread",cx+dx,cz+dz,ChunkStatus.CARVERS,true);VanillaQueryMain.server.await(future);
   if(!((ChunkResult<?>)future.join()).isSuccess())throw new IllegalStateException("CARVERS missing");
  }
  VanillaQueryMain.server.drain();context=(WorldGenContext)VanillaQueryMain.readField(source.chunkMap,"worldGenContext");
  var holders=new LinkedHashMap<Long,Holder>();
  for(int dz=-9;dz<=9;dz++)for(int dx=-9;dx<=9;dx++){
   var holder=(GenerationChunkHolder)VanillaQueryMain.invokeMethod(source.chunkMap,"getUpdatingChunkIfPresent",ChunkPos.asLong(cx+dx,cz+dz));
   holders.put(ChunkPos.asLong(cx+dx,cz+dz),new Holder((ProtoChunk)holder.getLatestChunk()));
  }
  VersionQueryObservation.reset(x,z);OBSERVE=false;return holders;
 }
 static Integer sparseHeight(Map<Long,Holder> holders)throws Exception {
  Integer height=null;int count=0;
  for(var start:holders.get(ChunkPos.asLong(cx,cz)).chunk.getAllStarts().values())if(start.isValid())for(var piece:start.getPieces())if(piece.getClass().getSimpleName().equals("SwampHutPiece")){height=(int)VanillaQueryMain.readField(piece,"heightPosition");count++;}
  if(count>1)throw new IllegalStateException("Multiple target huts");return height;
 }
 static JsonObject sparseQuery(JsonObject request)throws Exception {
  long begin=System.nanoTime(),gcTime=gcMillis(),gcCount=gcCollections(),seed=request.get("seed").getAsLong();int x=request.get("x").getAsInt(),z=request.get("z").getAsInt();
  var prefixes=new ArrayList<int[]>();for(var row:request.getAsJsonArray("prefixes")){var values=row.getAsJsonArray();int[] prefix=new int[values.size()];for(int i=0;i<prefix.length;i++)prefix[i]=values.get(i).getAsInt();prefixes.add(prefix);}
  var world=VanillaQueryMain.worldConfiguration(request);var trie=PrefixOrderExecutor.trie(prefixes);var holders=prepareSparse(seed,x,z,world);long prepared=System.nanoTime();Integer[] heights=new Integer[prefixes.size()];
  boolean audit=Boolean.getBoolean("hut.prefix.checkUndo");StateKey baseline=audit?stateKey(holders,0):null;
  var sparseCache=cache(holders);long[] stepTimes=new long[2];
  Object targetPiece=null;for(var start:holders.get(ChunkPos.asLong(cx,cz)).chunk.getAllStarts().values())if(start.isValid())for(var piece:start.getPieces())if(piece.getClass().getSimpleName().equals("SwampHutPiece"))targetPiece=piece;
  final Object centerTarget=targetPiece;
  var engine=new PrefixOrderExecutor.Engine(){
   public Object checkpoint(int index)throws Exception{return sparseCheckpoint(holders,index);}
   public void decorate(int index)throws Exception{long t=System.nanoTime();if(index==8)centerProbe(true,centerTarget);try{FeatureOrderEnumerator121.decorate(holders,sparseCache,cx+(index==8?0:NEIGHBORS[index][0]),cz+(index==8?0:NEIGHBORS[index][1]));}finally{if(index==8)centerProbe(false,null);stepTimes[index==8?1:0]+=System.nanoTime()-t;}}
   public Integer height()throws Exception{return sparseHeight(holders);}
   public void rollback(Object value)throws Exception{sparseRollback(holders,value);}
  };
  PrefixOrderExecutor.Statistics stats;
  JsonObject absence=absenceProof(holders);
  if(absence!=null){stats=new PrefixOrderExecutor.Statistics(0,0,0,0,0);}
  else if(!request.has("reuse_prefixes")||request.get("reuse_prefixes").getAsBoolean())stats=PrefixOrderExecutor.run(trie,engine,(id,prefix,height)->heights[id]=height);
  else {
   long neighbors=0,centers=0,checkpoint=0,decoration=0,rollback=0;
   for(int id=0;id<prefixes.size();id++){
    long t=System.nanoTime();var before=new MemoryCheckpoint(holders,cx,cz,2);checkpoint+=System.nanoTime()-t;
    try{t=System.nanoTime();for(int index:prefixes.get(id)){engine.decorate(index);neighbors++;}engine.decorate(8);centers++;heights[id]=engine.height();decoration+=System.nanoTime()-t;}
    finally{t=System.nanoTime();before.restore();rollback+=System.nanoTime()-t;}
   }
   stats=new PrefixOrderExecutor.Statistics(neighbors,centers,checkpoint,decoration,rollback);
  }
  if(audit&&!baseline.equals(stateKey(holders,0)))throw new IllegalStateException("Sparse traversal rollback differs");
  long end=System.nanoTime();var out=new JsonObject();if(request.has("id"))out.add("id",request.get("id"));out.addProperty("version",net.minecraft.SharedConstants.getCurrentVersion().getId());out.addProperty("seed",Long.toString(seed));out.addProperty("x",x);out.addProperty("z",z);out.addProperty("world_type",world.worldType());out.addProperty("controlled",world.controlled());if(world.worldType().equals("single_biome"))out.addProperty("biome",world.biome());else if(world.biome()!=null)out.addProperty("force_biome",world.biome());out.add("heights",NULL_JSON.toJsonTree(heights));out.addProperty("seconds",(end-begin)*1e-9);out.addProperty("base_seconds",(prepared-begin)*1e-9);out.addProperty("feature_seconds",(end-prepared)*1e-9);out.addProperty("neighbor_steps",stats.neighborSteps());out.addProperty("center_steps",stats.centerSteps());out.addProperty("executed_feature_steps",stats.neighborSteps()+stats.centerSteps());out.addProperty("checkpoint_seconds",stats.checkpointNanos()*1e-9);out.addProperty("decoration_seconds",stats.decorationNanos()*1e-9);out.addProperty("rollback_seconds",stats.rollbackNanos()*1e-9);out.addProperty("heap_used_bytes",Runtime.getRuntime().totalMemory()-Runtime.getRuntime().freeMemory());out.addProperty("section_cow",sectionCow);out.addProperty("skip_post_hut_features",SKIP_POST_HUT_FEATURES);out.addProperty("neighbor_decoration_seconds",stepTimes[0]*1e-9);out.addProperty("center_decoration_seconds",stepTimes[1]*1e-9);out.addProperty("gc_seconds",(gcMillis()-gcTime)*.001);out.addProperty("gc_collections",gcCollections()-gcCount);return out;
 }
 static long gcMillis(){long value=0;for(var bean:java.lang.management.ManagementFactory.getGarbageCollectorMXBeans())value+=Math.max(0,bean.getCollectionTime());return value;}
 static long gcCollections(){long value=0;for(var bean:java.lang.management.ManagementFactory.getGarbageCollectorMXBeans())value+=Math.max(0,bean.getCollectionCount());return value;}
 static void serve()throws Exception {
  var protocol=new java.io.PrintStream(new java.io.FileOutputStream(java.io.FileDescriptor.out),true,java.nio.charset.StandardCharsets.UTF_8);
  VanillaQueryMain.bootstrap();sectionCow=installSectionObserver();initializeCenterProbe();protocol.println("PREFIX_SERVICE_READY "+net.minecraft.SharedConstants.getCurrentVersion().getId());
  var reader=new java.io.BufferedReader(new java.io.InputStreamReader(System.in,java.nio.charset.StandardCharsets.UTF_8));String line;
  while((line=reader.readLine())!=null){if(line.isBlank())continue;JsonObject request=JsonParser.parseString(line).getAsJsonObject();try{protocol.println(NULL_JSON.toJson(sparseQuery(request)));}catch(Throwable error){var out=new JsonObject();if(request.has("id"))out.add("id",request.get("id"));out.addProperty("error",error.toString());protocol.println(out);error.printStackTrace(System.err);throw error;}}
  System.exit(0);
 }
 public static void main(String[] args)throws Exception {
  if(args.length!=1||!args[0].equals("--serve"))throw new IllegalArgumentException("--serve");
  serve();
 }
}
