import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
/** Shared task accounting for the dedicated generation process. */
public final class VersionQueryRuntime {
 public static volatile boolean enabled;
 public static final AtomicLong tasks=new AtomicLong();
 public static final AtomicLong generationClaims=new AtomicLong();
 public static final AtomicLong stages=new AtomicLong();
 private static final AtomicReference<Throwable> failure=new AtomicReference<>();
 private static final ConcurrentMap<String,long[]> profile=new ConcurrentHashMap<>();
 private static final ThreadLocal<ArrayDeque<Long>> stageStarted=ThreadLocal.withInitial(ArrayDeque::new);
 private static final ThreadLocal<ArrayDeque<Object>> stageNames=ThreadLocal.withInitial(ArrayDeque::new);
 private static final Map<ExecutorService,ExecutorService> wrappers=Collections.synchronizedMap(new IdentityHashMap<>());
 public static ExecutorService executor(ExecutorService original){
  if(!enabled)return original;
  synchronized(wrappers){return wrappers.computeIfAbsent(original,delegate->new AbstractExecutorService(){
   public void execute(Runnable task){tasks.incrementAndGet();try{delegate.execute(()->{try{task.run();}catch(Throwable e){failure.compareAndSet(null,e);throw e;}finally{tasks.decrementAndGet();}});}catch(Throwable e){tasks.decrementAndGet();throw e;}}
   public void shutdown(){throw new UnsupportedOperationException("Process owns executor");}
   public List<Runnable> shutdownNow(){throw new UnsupportedOperationException("Process owns executor");}
   public boolean isShutdown(){return delegate.isShutdown();}public boolean isTerminated(){return delegate.isTerminated();}
   public boolean awaitTermination(long t,TimeUnit u)throws InterruptedException{return delegate.awaitTermination(t,u);}
  });}
 }
 public static void claim(){generationClaims.incrementAndGet();}
 public static void release(){generationClaims.decrementAndGet();}
 public static void stageBegin(Object step){stageStarted.get().push(System.nanoTime());stageNames.get().push(step);}
 public static Object stage(Object value){
  long started=stageStarted.get().pop();String name=stageName(stageNames.get().pop());
  stages.incrementAndGet();((CompletableFuture<?>)value).whenComplete((r,error)->{if(error!=null)failure.compareAndSet(null,error);long[] row=profile.computeIfAbsent(name,k->new long[2]);synchronized(row){row[0]++;row[1]+=System.nanoTime()-started;}stages.decrementAndGet();});return value;
 }
 private static String stageName(Object step){try{Object status=step;try{status=step.getClass().getMethod("targetStatus").invoke(step);}catch(NoSuchMethodException legacy){}try{return String.valueOf(status.getClass().getMethod("getName").invoke(status));}catch(NoSuchMethodException legacy){return status.toString();}}catch(Exception e){throw new IllegalStateException(e);}}
 public static void resetProfile(){profile.clear();}
 public static Map<String,long[]> profile(){return new TreeMap<>(profile);}
 public static void checkFailure(){Throwable e=failure.get();if(e!=null)throw new CompletionException(e);}
}
