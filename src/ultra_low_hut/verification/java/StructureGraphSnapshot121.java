import java.lang.reflect.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicLong;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Holder;
import net.minecraft.resources.ResourceKey;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.levelgen.structure.*;
import net.minecraft.world.level.levelgen.structure.pieces.StructurePieceType;
import net.minecraft.world.level.levelgen.structure.templatesystem.*;

/** In-place undo of a 1.21 structure graph. Unknown mutable classes fail closed. */
@SuppressWarnings({"rawtypes","unchecked"})
public final class StructureGraphSnapshot121 {
 private record Identity(Object value) {
  public boolean equals(Object other){return other instanceof Identity i&&value==i.value;}
  public int hashCode(){return System.identityHashCode(value);}
 }
 private interface Undo {void restore()throws Exception;}
 private static final Map<Class<?>,List<Field>> FIELDS=new java.util.concurrent.ConcurrentHashMap<>();
 private static List<Field> fields(Class<?> type){return FIELDS.computeIfAbsent(type,t->{
  var result=new ArrayList<Field>();for(Class<?> c=t;c!=Object.class;c=c.getSuperclass())for(Field f:c.getDeclaredFields())if(!Modifier.isStatic(f.getModifiers())){f.setAccessible(true);result.add(f);}
  result.sort(Comparator.comparing(f->f.getDeclaringClass().getName()+"."+f.getName()));return List.copyOf(result);
 });}
 private final List<Undo> undo=new ArrayList<>();
 private final List<Object> key=new ArrayList<>();
 private final Set<Object> visited=Collections.newSetFromMap(new IdentityHashMap<>());
 public StructureGraphSnapshot121(Collection<?> roots)throws Exception {int i=0;for(Object root:roots)capture(root,"root["+(i++)+"]");}
 public List<Object> key(){return Collections.unmodifiableList(key);}
 public void restore()throws Exception {for(Undo entry:undo)entry.restore();}
 // In FEATURES, the template manager only reads constant resources or populates
 // deterministic load/filter caches. No reload/save/remove occurs; placement
 // copies source NBT. Per-piece settings and mutable element graphs stay in undo.
 private static boolean immutable(Object o){
  return o==null||o instanceof String||o instanceof Enum<?>||(o instanceof Byte||o instanceof Short||o instanceof Integer||o instanceof Long||o instanceof Float||o instanceof Double)||o instanceof Boolean||o instanceof Character||o instanceof Class<?>||o instanceof ResourceKey<?>||o instanceof Holder<?>||o instanceof BlockState||o instanceof Structure||o instanceof StructurePieceType||o instanceof StructureTemplate||o instanceof StructureTemplateManager||o instanceof StructureProcessor||o instanceof BlockPos&&!(o instanceof BlockPos.MutableBlockPos);
 }
 private static boolean immutableContainer(Object o){String n=o.getClass().getName();return n.contains("Immutable")||n.contains("Unmodifiable")||n.contains("Singleton")||n.contains("Empty");}
 private Object valueKey(Object o){
  if(o instanceof BoundingBox b)return List.of(b.minX(),b.minY(),b.minZ(),b.maxX(),b.maxY(),b.maxZ());
  return immutable(o)?o:new Identity(o);
 }
 private void capture(Object object,String path)throws Exception {
  if(immutable(object)||!visited.add(object))return;
  key.add(object instanceof BoundingBox?"BoundingBox":new Identity(object));
  if(object instanceof java.util.concurrent.atomic.AtomicInteger atomic){int value=atomic.get();key.add(value);undo.add(()->atomic.set(value));return;}
  if(object instanceof AtomicLong atomic){long value=atomic.get();key.add(value);undo.add(()->atomic.set(value));return;}
  Class<?> type=object.getClass();
  if(type.isArray()){
   int length=Array.getLength(object);Object copy=Array.newInstance(type.getComponentType(),length);System.arraycopy(object,0,copy,0,length);undo.add(()->System.arraycopy(copy,0,object,0,length));
   key.add(length);for(int i=0;i<length;i++){Object value=Array.get(copy,i);key.add(valueKey(value));capture(value,path+"["+i+"]");}return;
  }
  if(object instanceof Optional<?> optional){capture(optional.orElse(null),path+".optional");return;}
  if(object instanceof com.mojang.datafixers.util.Either<?,?> either){
   Optional<?> left=either.left();capture(left.isPresent()?left.get():either.right().orElse(null),path+(left.isPresent()?".left":".right"));return;
  }
  if(object instanceof Map<?,?> map){
   var values=new LinkedHashMap<Object,Object>();for(var e:map.entrySet()){values.put(e.getKey(),e.getValue());key.add(valueKey(e.getKey()));key.add(valueKey(e.getValue()));capture(e.getKey(),path+".mapKey");capture(e.getValue(),path+".mapValue");}
   if(!immutableContainer(map))undo.add(()->{((Map)map).clear();((Map)map).putAll(values);});return;
  }
  if(object instanceof Collection<?> collection){
   var values=new ArrayList<>(collection);key.add(values.size());for(int i=0;i<values.size();i++){Object value=values.get(i);key.add(valueKey(value));capture(value,path+"["+i+"]");}
   if(!immutableContainer(collection))undo.add(()->{((Collection)collection).clear();((Collection)collection).addAll(values);});return;
  }
  if(!type.getName().startsWith("net.minecraft."))throw new IllegalStateException("Unsupported structure state class: "+type.getName()+" at "+path);
  for(Field field:fields(type)){Object value=field.get(object);key.add(field);key.add(valueKey(value));if(!Modifier.isFinal(field.getModifiers()))undo.add(()->field.set(object,value));capture(value,path+"."+field.getDeclaringClass().getSimpleName()+"."+field.getName());}
 }
}
