import com.google.gson.*;
import java.nio.file.*;
import java.util.concurrent.CompletableFuture;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ChunkResult;
import net.minecraft.tags.FluidTags;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.chunk.ChunkAccess;
import net.minecraft.world.level.chunk.status.ChunkStatus;
/** Capture natural CARVERS terrain for the shared layout comparison. */
public final class NaturalTerrainSnapshot {
 public static void main(String[] args) throws Exception {
  VanillaQueryMain.bootstrap();
  JsonArray panel=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonArray();
  for(JsonElement element:panel){
   JsonObject row=element.getAsJsonObject();Path path=Path.of(row.get("snapshot_file").getAsString());
   if(Files.exists(path)&&Files.size(path)==16*16*384)continue;
   if(VanillaQueryMain.server!=null){VanillaQueryMain.server.drain();VanillaQueryMain.server.overworld().close();VanillaQueryMain.server.drain();VanillaQueryMain.server=null;}
   long seed=row.get("seed").getAsLong();int x=row.get("x").getAsInt(),z=row.get("z").getAsInt();
   VanillaQueryMain.server=VanillaQueryMain.createWorldContext(seed,null,"normal");
   var server=VanillaQueryMain.server;
   var future=(CompletableFuture<?>)VanillaQueryMain.invokeMethod(server.overworld().getChunkSource(),"getChunkFutureMainThread",x>>4,z>>4,ChunkStatus.CARVERS,true);
   server.await(future);server.drain();
   var chunk=((ChunkResult<ChunkAccess>)future.join()).orElseThrow(()->new IllegalStateException("CARVERS chunk missing"));
   byte[] raw=new byte[16*16*384];BlockPos.MutableBlockPos pos=new BlockPos.MutableBlockPos();
   for(int dz=0;dz<16;dz++)for(int dx=0;dx<16;dx++)for(int y=-64;y<320;y++){
    var b=chunk.getBlockState(pos.set(x+dx,y,z+dz));
    byte v=b.isAir()?(byte)0:b.is(Blocks.BEDROCK)?(byte)4:b.getFluidState().isEmpty()?(byte)1:b.getFluidState().is(FluidTags.LAVA)?(byte)3:(byte)2;
    raw[(dz*16+dx)*384+y+64]=v;
   }
   Files.write(path,raw);System.out.println("{\"snapshot\":\""+row.get("id").getAsString()+"\"}");System.out.flush();
  }
  System.exit(0);
 }
}
