import java.lang.reflect.*;
import java.net.Proxy;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.LockSupport;
import com.google.gson.*;
import com.mojang.authlib.GameProfile;
import com.mojang.authlib.yggdrasil.YggdrasilAuthenticationService;
import net.minecraft.SharedConstants;
import net.minecraft.SystemReport;
import net.minecraft.Util;
import net.minecraft.commands.Commands;
import net.minecraft.core.registries.Registries;
import net.minecraft.server.*;
import net.minecraft.server.level.*;
import net.minecraft.server.level.progress.*;
import net.minecraft.server.packs.repository.*;
import net.minecraft.server.players.PlayerList;
import net.minecraft.util.datafix.DataFixers;
import net.minecraft.util.debugchart.*;
import net.minecraft.world.Difficulty;
import net.minecraft.world.level.*;
import net.minecraft.world.level.biome.*;
import net.minecraft.world.level.chunk.*;
import net.minecraft.world.level.chunk.status.*;
import net.minecraft.world.level.dimension.*;
import net.minecraft.world.level.levelgen.*;
import net.minecraft.world.level.levelgen.presets.WorldPresets;
import net.minecraft.world.level.storage.*;

/** Vanilla generation hosted by an IPC loop instead of the game-server lifecycle. */
public final class VanillaQueryMain {
 static final sun.misc.Unsafe U=getUnsafe();
 static WorldStem stem;static PackRepository packs;
 static Services services;
 static QueryServer server;
 static Long contextSeed;static String contextBiome;
 static sun.misc.Unsafe getUnsafe(){try{Field f=sun.misc.Unsafe.class.getDeclaredField("theUnsafe");f.setAccessible(true);return(sun.misc.Unsafe)f.get(null);}catch(Exception e){throw new ExceptionInInitializerError(e);}}
 static <T>T allocateWithoutConstructor(Class<T> c)throws Exception{return c.cast(U.allocateInstance(c));}
 static Field findField(Class<?> c,String n)throws Exception{for(;c!=null;c=c.getSuperclass())try{Field f=c.getDeclaredField(n);f.setAccessible(true);return f;}catch(NoSuchFieldException e){}throw new NoSuchFieldException(n);}
 static void writeField(Object o,String n,Object v)throws Exception{findField(o.getClass(),n).set(o,v);}
 static Object readField(Object o,String n)throws Exception{return findField(o.getClass(),n).get(o);}
 static Object invokeMethod(Object o,String n,Object... a)throws Exception{
  for(Class<?> c=o.getClass();c!=null;c=c.getSuperclass())for(Method m:c.getDeclaredMethods())if(m.getName().equals(n)&&m.getParameterCount()==a.length){m.setAccessible(true);try{return m.invoke(o,a);}catch(InvocationTargetException e){throw new IllegalStateException(e.getCause());}}throw new NoSuchMethodException(n);
 }
 static void bootstrap()throws Exception{
  SharedConstants.tryDetectVersion();Bootstrap.bootStrap();packs=ServerPacksSource.createVanillaTrustedRepository();
  var config=new WorldLoader.InitConfig(new WorldLoader.PackConfig(packs,WorldDataConfiguration.DEFAULT,false,true),Commands.CommandSelection.DEDICATED,2);
  stem=Util.<WorldStem>blockUntilDone(executor->WorldLoader.load(config,context->{
   var settings=new LevelSettings("query",GameType.SURVIVAL,false,Difficulty.NORMAL,false,new GameRules(),context.dataConfiguration());
   var dims=WorldPresets.createNormalWorldDimensions(context.datapackWorldgen()).bake(context.datapackDimensions().registryOrThrow(Registries.LEVEL_STEM));
   return new WorldLoader.DataLoadOutput<>(new PrimaryLevelData(settings,new WorldOptions(0,true,false),dims.specialWorldProperty(),dims.lifecycle()),dims.dimensionsRegistryAccess());
  },WorldStem::new,Util.backgroundExecutor(),executor)).get();
  VersionQueryRuntime.enabled=true;
  var auth=new YggdrasilAuthenticationService(Proxy.NO_PROXY);
  services=new Services(auth.createMinecraftSessionService(),auth.getServicesKeySet(),auth.createProfileRepository(),null);
 }
 static LevelStorageSource.LevelStorageAccess createMemoryStorage()throws Exception{
  // Only hosting metadata: no LevelStorageSource or LevelStorageAccess constructor runs.
  Path sentinel=Path.of("__vanilla_query_memory__");
  var source=allocateWithoutConstructor(LevelStorageSource.class);writeField(source,"fixerUpper",DataFixers.getDataFixer());writeField(source,"baseDir",sentinel);writeField(source,"backupDir",sentinel);
  var access=allocateWithoutConstructor(LevelStorageSource.LevelStorageAccess.class);writeField(access,"this$0",source);writeField(access,"levelDirectory",new LevelStorageSource.LevelDirectory(sentinel));writeField(access,"levelId","query");writeField(access,"resources",new HashMap<>());return access;
 }
 static final ChunkProgressListener PROGRESS=new ChunkProgressListener(){public void updateSpawnPos(ChunkPos p){}public void onStatusChange(ChunkPos p,ChunkStatus s){}public void start(){}public void stop(){}};
 static final class QueryServer extends MinecraftServer {
  final LocalSampleLogger samples=new LocalSampleLogger(4);
  QueryServer(WorldStem state,LevelStorageSource.LevelStorageAccess storage,Services services)throws Exception{
   super(Thread.currentThread(),storage,packs,state,Proxy.NO_PROXY,DataFixers.getDataFixer(),services,radius->PROGRESS);
   setPlayerList(new PlayerList(this,registries(),playerDataStorage,0){});
  }
  void install(String forced)throws Exception{
   var original=registryAccess().registryOrThrow(Registries.LEVEL_STEM).getOrThrow(LevelStem.OVERWORLD);
   var g=(NoiseBasedChunkGenerator)original.generator();BiomeSource b=g.getBiomeSource();
   if(forced!=null)b=new FixedBiomeSource(registryAccess().registryOrThrow(Registries.BIOME).getHolderOrThrow(net.minecraft.resources.ResourceKey.create(Registries.BIOME,net.minecraft.resources.ResourceLocation.parse(forced))));
   LevelStem dimension=new LevelStem(original.type(),new NoiseBasedChunkGenerator(b,g.generatorSettings()));
   var data=getWorldData().overworldData();data.setInitialized(true);
   var level=new ServerLevel(this,Util.backgroundExecutor(),storageSource,data,Level.OVERWORLD,dimension,PROGRESS,false,BiomeManager.obfuscateSeed(getWorldData().worldGenOptions().seed()),List.of(),true,null);
   ((Map)readField(this,"levels")).put(Level.OVERWORLD,level);writeField(this,"commandStorage",new CommandStorage(level.getDataStorage()));
   invokeMethod(this,"readScoreboard",level.getDataStorage());
  }
  boolean pump(){boolean a=super.pollTask();boolean b=overworld()!=null&&overworld().getChunkSource().pollTask();return a||b;}
  void await(CompletableFuture<?> future)throws Exception{
   long deadline=System.nanoTime()+120_000_000_000L;
   while(!future.isDone()){VersionQueryRuntime.checkFailure();if(System.nanoTime()>deadline)throw new TimeoutException("Generation request timed out");if(!pump())LockSupport.parkNanos(100_000);}
   future.join();
  }
  void drain()throws Exception{
   long deadline=System.nanoTime()+120_000_000_000L;
   for(;;){VersionQueryRuntime.checkFailure();boolean did=pump();if(VersionQueryRuntime.tasks.get()==0&&VersionQueryRuntime.generationClaims.get()==0&&VersionQueryRuntime.stages.get()==0&&!did){
     if(!pump()&&VersionQueryRuntime.tasks.get()==0&&VersionQueryRuntime.generationClaims.get()==0&&VersionQueryRuntime.stages.get()==0)return;
    }
    if(System.nanoTime()>deadline)throw new TimeoutException("Generation did not drain: tasks="+VersionQueryRuntime.tasks+" claims="+VersionQueryRuntime.generationClaims);
    if(!did)LockSupport.parkNanos(100_000);
   }
  }
  ChunkAccess generate(int x,int z)throws Exception{
   var source=overworld().getChunkSource();var future=(CompletableFuture<?>)invokeMethod(source,"getChunkFutureMainThread",x,z,ChunkStatus.FULL,true);await(future);
   ChunkAccess result=((ChunkResult<ChunkAccess>)future.join()).orElseThrow(()->new IllegalStateException("Chunk unavailable"));
   // This vanilla continuation contains generation-time block/fluid postprocessing.
   Object holder=invokeMethod(source.chunkMap,"getVisibleChunkIfPresent",ChunkPos.asLong(x,z));
   await(source.chunkMap.prepareTickingChunk((ChunkHolder)holder));drain();await(source.getLightEngine().waitForPendingTasks(x,z));drain();return result;
  }
  @Override protected boolean shouldRun(TickTask task){return true;}
  @Override public boolean pollTask(){return pump();}
  @Override protected boolean initServer(){throw new UnsupportedOperationException();}
  @Override public int getOperatorUserPermissionLevel(){return 4;}
  @Override public int getFunctionCompilationLevel(){return 2;}
  @Override public boolean shouldRconBroadcast(){return false;}
  @Override protected SampleLogger getTickTimeLogger(){return samples;}
  @Override public boolean isTickTimeLoggingEnabled(){return false;}
  @Override public SystemReport fillServerSystemReport(SystemReport r){return r;}
  @Override public boolean isDedicatedServer(){return false;}
  @Override public int getRateLimitPacketsPerSecond(){return 0;}
  @Override public boolean isEpollEnabled(){return false;}
  @Override public boolean isCommandBlockEnabled(){return false;}
  @Override public boolean isPublished(){return false;}
  @Override public boolean shouldInformAdmins(){return false;}
  @Override public boolean isSingleplayerOwner(GameProfile p){return false;}
 }
 static QueryServer createWorldContext(long seed,String forced)throws Exception{
  var base=(PrimaryLevelData)stem.worldData();
  var data=new PrimaryLevelData((LevelSettings)readField(base,"settings"),new WorldOptions(seed,true,false),PrimaryLevelData.SpecialWorldProperty.NONE,com.mojang.serialization.Lifecycle.stable());
  var state=new WorldStem(stem.resourceManager(),stem.dataPackResources(),stem.registries(),data);
  QueryServer query=new QueryServer(state,createMemoryStorage(),services);query.install(forced);return query;
 }
 static JsonObject processRequest(JsonObject input)throws Exception{
  if(input.has("requests")){JsonArray output=new JsonArray();for(JsonElement e:input.getAsJsonArray("requests"))output.add(processRequest(e.getAsJsonObject()));JsonObject result=new JsonObject();result.add("responses",output);return result;}
  long t=System.nanoTime();long seed=input.get("seed").getAsLong();int x=input.get("x").getAsInt(),z=input.get("z").getAsInt();
  String forced=input.has("force_biome")?input.get("force_biome").getAsString():null;
  boolean reused=server!=null&&Objects.equals(contextSeed,seed)&&Objects.equals(contextBiome,forced)&&input.has("reuse")&&input.get("reuse").getAsBoolean();
  if(server!=null&&!reused){server.drain();server.overworld().close();server.drain();server=null;}
  VersionQueryRuntime.resetProfile();
  if(!reused){server=createWorldContext(seed,forced);contextSeed=seed;contextBiome=forced;}
  VersionQueryObservation.reset(x,z);
  int cx=Math.floorDiv(x,16),cz=Math.floorDiv(z,16);
  String approach=input.has("approach")?input.get("approach").getAsString():"center";
  if(approach.equals("east")||approach.equals("west"))server.generate(cx+(approach.equals("east")?2:-2),cz);
  ChunkAccess chunk=server.generate(cx,cz);
  JsonObject result=new JsonObject();result.addProperty("seed",Long.toString(seed));result.addProperty("x",x);result.addProperty("z",z);JsonArray heights=new JsonArray(),pieces=new JsonArray();
  for(var start:chunk.getAllStarts().values())if(start.isValid())for(var piece:start.getPieces())if(Set.of("SwampHutPiece","SwamplandHutPiece").contains(piece.getClass().getSimpleName())){int h=(int)readField(piece,"heightPosition");heights.add(h);JsonObject p=new JsonObject();p.addProperty("HPos",h);p.addProperty("bbox",piece.getBoundingBox().toString());pieces.add(p);}
  result.add("heights",heights);result.add("hut_pieces",pieces);result.add("before_hut_calls",VersionQueryObservation.result());result.addProperty("world_reused",reused);
  result.addProperty("version",System.getProperty("hut.service.version"));result.addProperty("generation_status","FULL_AND_POSTPROCESS");
  result.addProperty("controlled",forced!=null);if(forced!=null)result.addProperty("force_biome",forced);
  if(input.has("operation")&&input.get("operation").getAsString().equals("terrain"))result.add("terrain",queryTerrain(input,x,z));
  if(input.has("digest")&&input.get("digest").getAsBoolean())result.addProperty("block_digest",computeTerrainDigest(chunk));
  result.addProperty("seconds",(System.nanoTime()-t)*1e-9);result.addProperty("tasks",VersionQueryRuntime.tasks.get());result.addProperty("generation_claims",VersionQueryRuntime.generationClaims.get());result.addProperty("active_stages",VersionQueryRuntime.stages.get());JsonArray profile=new JsonArray();for(var entry:VersionQueryRuntime.profile().entrySet()){JsonObject row=new JsonObject();row.addProperty("stage",entry.getKey());row.addProperty("chunks",entry.getValue()[0]);row.addProperty("async_seconds",entry.getValue()[1]*1e-9);profile.add(row);}result.add("profile",profile);if(Files.exists(Path.of("__vanilla_query_memory__")))throw new IllegalStateException("Unexpected world storage creation");return result;
 }
 static String computeTerrainDigest(ChunkAccess chunk)throws Exception{
  var digest=java.security.MessageDigest.getInstance("SHA-256");var pos=new net.minecraft.core.BlockPos.MutableBlockPos();
  int min=chunk.getMinBuildHeight(),max=chunk.getMaxBuildHeight();
  for(int y=min;y<max;y++)for(int z=0;z<16;z++)for(int x=0;x<16;x++){
   int id=net.minecraft.world.level.block.Block.BLOCK_STATE_REGISTRY.getId(chunk.getBlockState(pos.set(x,y,z)));
   digest.update((byte)(id>>>24));digest.update((byte)(id>>>16));digest.update((byte)(id>>>8));digest.update((byte)id);
  }
  return HexFormat.of().formatHex(digest.digest());
 }
 static JsonObject queryTerrain(JsonObject input,int x,int z)throws Exception{
  int width=input.has("width")?input.get("width").getAsInt():1,depth=input.has("depth")?input.get("depth").getAsInt():1;
  if(width<1||depth<1||(long)width*depth>4096)throw new IllegalArgumentException("Rectangle must contain 1..4096 columns");
  Set<Long> generated=new HashSet<>();JsonArray columns=new JsonArray();
  for(int dz=0;dz<depth;dz++)for(int dx=0;dx<width;dx++){
   int xx=x+dx,zz=z+dz,cx=Math.floorDiv(xx,16),cz=Math.floorDiv(zz,16);long key=((long)cx<<32)^(cz&0xffffffffL);
   if(generated.add(key))server.generate(cx,cz);
   JsonObject column=new JsonObject();column.addProperty("x",xx);column.addProperty("z",zz);column.addProperty("height",server.overworld().getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES,xx,zz));
   if(input.has("sample_y")){JsonArray blocks=new JsonArray();for(var value:input.getAsJsonArray("sample_y")){int y=value.getAsInt();JsonObject block=new JsonObject();block.addProperty("y",y);block.addProperty("state",server.overworld().getBlockState(new net.minecraft.core.BlockPos(xx,y,zz)).toString());blocks.add(block);}column.add("blocks",blocks);}columns.add(column);
  }
  JsonObject terrain=new JsonObject();terrain.addProperty("heightmap","MOTION_BLOCKING_NO_LEAVES");terrain.add("columns",columns);return terrain;
 }
 public static void main(String[] args)throws Exception{
  bootstrap();Path root=Path.of(System.getProperty("hut.service.root"));for(String name:List.of("inbox","outbox","processed"))Files.createDirectories(root.resolve(name));
  Files.writeString(root.resolve("ready.json"),"{\"engine\":\"vanilla-memory-generation\",\"pid\":"+ProcessHandle.current().pid()+"}");
  for(;;){Path request;try(var paths=Files.list(root.resolve("inbox"))){request=paths.filter(p->p.toString().endsWith(".json")).sorted().findFirst().orElse(null);}if(request==null){Thread.sleep(20);continue;}
   JsonObject result;try{result=processRequest(JsonParser.parseString(Files.readString(request)).getAsJsonObject());}catch(Throwable e){e.printStackTrace();result=new JsonObject();result.addProperty("error",e.toString());}
   Path tmp=root.resolve("outbox/"+request.getFileName()+".tmp");Files.writeString(tmp,result.toString());Files.move(tmp,root.resolve("outbox/"+request.getFileName()),StandardCopyOption.ATOMIC_MOVE);Files.move(request,root.resolve("processed/"+request.getFileName()));
   if(result.has("error"))System.exit(1);
  }
 }
}
