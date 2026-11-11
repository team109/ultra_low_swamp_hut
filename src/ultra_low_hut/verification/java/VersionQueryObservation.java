import java.lang.reflect.*;
import java.util.*;
import com.google.gson.*;
/** Records values already read by the vanilla hut-height method. */
public final class VersionQueryObservation {
 private static volatile int x,z;
 private static final List<JsonObject> events=Collections.synchronizedList(new ArrayList<>());
 private static final List<JsonArray> features=Collections.synchronizedList(new ArrayList<>());
 private static final ThreadLocal<JsonArray> columns=new ThreadLocal<>();
 private static final ThreadLocal<JsonArray> positions=new ThreadLocal<>();
 private static final ThreadLocal<Boolean> heightProbe=new ThreadLocal<>();
 public static void reset(int targetX,int targetZ){x=targetX;z=targetZ;events.clear();features.clear();}
 /** Entry into vanilla biome decoration, rather than the order of chunk requests. */
 public static void feature(Object chunk){
  try{Object pos=call(chunk,"getPos");JsonArray p=new JsonArray();p.add(coordinate(pos,"x"));p.add(coordinate(pos,"z"));features.add(p);}catch(Exception e){throw new IllegalStateException(e);}
 }
 private static int coordinate(Object pos,String name)throws Exception{try{return pos.getClass().getField(name).getInt(pos);}catch(NoSuchFieldException record){return ((Number)call(pos,name)).intValue();}}
 public static JsonArray featureOrder(){JsonArray result=new JsonArray();synchronized(features){for(JsonArray p:features)result.add(p);}return result;}
 static Object call(Object o,String method)throws Exception{return o.getClass().getMethod(method).invoke(o);}
 public static void begin(Object piece){
  heightProbe.set(VersionQueryRuntime.centerProbeActive&&piece==VersionQueryRuntime.centerTargetPiece);
  columns.remove();positions.remove();
  if(!Set.of("SwampHutPiece","SwamplandHutPiece").contains(piece.getClass().getSimpleName()))return;
  try{Object box=call(piece,"getBoundingBox");if((int)call(box,"minX")!=x||(int)call(box,"minZ")!=z)return;columns.set(new JsonArray());positions.set(new JsonArray());}catch(Exception e){throw new IllegalStateException(e);}
 }
 public static Object sample(Object blockPos){
  JsonArray values=columns.get();if(values!=null)try{values.add((Number)call(blockPos,"getY"));JsonArray p=new JsonArray();p.add((Number)call(blockPos,"getX"));p.add((Number)call(blockPos,"getZ"));positions.get().add(p);}catch(Exception e){throw new IllegalStateException(e);}return blockPos;
 }
 public static void end(){
  if(Boolean.TRUE.equals(heightProbe.get()))VersionQueryRuntime.centerHeightReady=true;
  heightProbe.remove();
  JsonArray values=columns.get();if(values==null)return;
  JsonObject event=new JsonObject();event.add("columns",values);event.add("positions",positions.get());int sum=0;for(JsonElement v:values)sum+=v.getAsInt();event.addProperty("sum",sum);if(values.size()>0)event.addProperty("mean",sum/values.size());events.add(event);columns.remove();positions.remove();
 }
 public static JsonArray result(){JsonArray result=new JsonArray();synchronized(events){for(JsonObject e:events)result.add(e);}return result;}
}
