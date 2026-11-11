import java.util.*;

/** A sparse prefix trie: evaluate center once per node and reuse each neighbor edge. */
public final class PrefixOrderExecutor {
 public interface Engine {
  Object checkpoint(int index)throws Exception;
  void decorate(int index)throws Exception;
  Integer height()throws Exception;
  void rollback(Object checkpoint)throws Exception;
 }
 public interface Sink {void accept(int id,int[] prefix,Integer height)throws Exception;}
 public static final class Node {
  final Node[] children=new Node[8]; int id=-1; int[] prefix;
 }
 public record Statistics(long neighborSteps,long centerSteps,long checkpointNanos,long decorationNanos,long rollbackNanos){}
 public static Node trie(List<int[]> prefixes){
  if(prefixes.isEmpty())throw new IllegalArgumentException("At least one measured prefix is required");
  Node root=new Node();int id=0;
  for(int[] prefix:prefixes){Node node=root;int used=0;for(int index:prefix){if(index<0||index>=8||(used&(1<<index))!=0)throw new IllegalArgumentException("Invalid neighbor prefix");used|=1<<index;if(node.children[index]==null)node.children[index]=new Node();node=node.children[index];}if(node.id>=0)throw new IllegalArgumentException("Duplicate prefix");node.id=id++;node.prefix=prefix.clone();}
  return root;
 }
 private final Engine engine;private final Sink sink;private long neighbors,centers,checkpointNanos,decorationNanos,rollbackNanos;
 private PrefixOrderExecutor(Engine engine,Sink sink){this.engine=engine;this.sink=sink;}
 public static Statistics run(Node root,Engine engine,Sink sink)throws Exception{var run=new PrefixOrderExecutor(engine,sink);run.visit(root);return new Statistics(run.neighbors,run.centers,run.checkpointNanos,run.decorationNanos,run.rollbackNanos);}
 private Object checkpoint(int index)throws Exception{long t=System.nanoTime();Object result=engine.checkpoint(index);checkpointNanos+=System.nanoTime()-t;return result;}
 private void decorate(int index)throws Exception{long t=System.nanoTime();engine.decorate(index);decorationNanos+=System.nanoTime()-t;}
 private void rollback(Object state)throws Exception{long t=System.nanoTime();engine.rollback(state);rollbackNanos+=System.nanoTime()-t;}
 private void visit(Node node)throws Exception{
  Object before;
  if(node.id>=0){before=checkpoint(8);try{decorate(8);centers++;sink.accept(node.id,node.prefix,engine.height());}finally{rollback(before);}}
  for(int index=0;index<8;index++)if(node.children[index]!=null){before=checkpoint(index);try{decorate(index);neighbors++;visit(node.children[index]);}finally{rollback(before);}}
 }
}
