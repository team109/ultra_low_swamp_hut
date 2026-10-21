import java.lang.reflect.*;
import java.util.*;
import com.google.gson.*;
/** Records values already read by the vanilla hut-height method. */
public final class VersionQueryObservation {
 private static volatile int x,z;
 private static final List<JsonObject> events=Collections.synchronizedList(new ArrayList<>());
 private static final ThreadLocal<JsonArray> columns=new ThreadLocal<>();
 private static final ThreadLocal<JsonArray> positions=new ThreadLocal<>();
 public static void reset(int targetX,int targetZ){x=targetX;z=targetZ;events.clear();}
 static Object call(Object o,String method)throws Exception{return o.getClass().getMethod(method).invoke(o);}
 public static void begin(Object piece){
  columns.remove();positions.remove();
  if(!Set.of("SwampHutPiece","SwamplandHutPiece").contains(piece.getClass().getSimpleName()))return;
  try{Object box=call(piece,"getBoundingBox");if((int)call(box,"minX")!=x||(int)call(box,"minZ")!=z)return;columns.set(new JsonArray());positions.set(new JsonArray());}catch(Exception e){throw new IllegalStateException(e);}
 }
 public static Object sample(Object blockPos){
  JsonArray values=columns.get();if(values!=null)try{values.add((Number)call(blockPos,"getY"));JsonArray p=new JsonArray();p.add((Number)call(blockPos,"getX"));p.add((Number)call(blockPos,"getZ"));positions.get().add(p);}catch(Exception e){throw new IllegalStateException(e);}return blockPos;
 }
 public static void end(){
  JsonArray values=columns.get();if(values==null)return;
  JsonObject event=new JsonObject();event.add("columns",values);event.add("positions",positions.get());int sum=0;for(JsonElement v:values)sum+=v.getAsInt();event.addProperty("sum",sum);if(values.size()>0)event.addProperty("mean",sum/values.size());events.add(event);columns.remove();positions.remove();
 }
 public static JsonArray result(){JsonArray result=new JsonArray();synchronized(events){for(JsonObject e:events)result.add(e);}return result;}
}
