import java.lang.instrument.*;
import java.security.ProtectionDomain;
import org.objectweb.asm.*;
/** Hosting, storage and optional rollback seams; generation executes official bytecode. */
public final class VersionQueryAgent {
 public static void premain(String args,Instrumentation instrumentation){
  instrumentation.addTransformer(new ClassFileTransformer(){public byte[] transform(ClassLoader loader,String name,Class<?> type,ProtectionDomain domain,byte[] bytes){
   if(!name.startsWith("net/minecraft/"))return null;
   String simple=name.substring(name.lastIndexOf('/')+1);
   if(!java.util.Set.of("ChunkStorage","SimpleRegionStorage","DimensionDataStorage","SavedDataStorage","LevelStorageSource$LevelStorageAccess","StructureTemplateManager","IOWorker","ScatteredFeaturePiece","GenerationChunkHolder","ChunkStep","ChunkStatus","ServerChunkCache","PlayerDataStorage","ChunkMap","Util","TracingExecutor","NoiseBasedChunkGenerator","ChunkGenerator","LevelChunkSection","PlacedFeature").contains(simple))return null;
   ClassReader reader=new ClassReader(bytes);ClassWriter writer=new ClassWriter(ClassWriter.COMPUTE_MAXS);
   reader.accept(new ClassVisitor(Opcodes.ASM9,writer){
    public MethodVisitor visitMethod(int access,String method,String desc,String signature,String[] exceptions){
     MethodVisitor output=super.visitMethod(access,method,desc,signature,exceptions);
     boolean storage=name.equals("net/minecraft/world/level/chunk/storage/ChunkStorage")||name.equals("net/minecraft/world/level/chunk/storage/SimpleRegionStorage");
     boolean saved=name.equals("net/minecraft/world/level/storage/DimensionDataStorage")||name.equals("net/minecraft/world/level/storage/SavedDataStorage");
     boolean accessClass=name.endsWith("/LevelStorageSource$LevelStorageAccess");
     boolean templates=name.endsWith("/StructureTemplateManager");
     boolean io=name.equals("net/minecraft/world/level/chunk/storage/IOWorker");
     boolean height=name.endsWith("/ScatteredFeaturePiece")&&method.equals("updateAverageGroundHeight");
     // BulkSectionAccess locks the palette before writing. Copy before acquire
     // as well, so its matching release always targets the same palette.
     boolean sectionWrite=name.endsWith("/LevelChunkSection")&&(method.equals("setBlockState")||method.equals("acquire"))
       &&(access&Opcodes.ACC_STATIC)==0;
     boolean stage=(name.endsWith("/ChunkStep")&&method.equals("apply"))||(name.endsWith("/ChunkStatus")&&method.equals("generate"));
     if(name.endsWith("/NoiseBasedChunkGenerator")&&method.equals("spawnOriginalMobs")&&Boolean.parseBoolean(System.getProperty("hut.query.skipInitialMobs","true"))){output.visitCode();output.visitInsn(Opcodes.RETURN);output.visitMaxs(0,0);output.visitEnd();return null;}
     if(io&&method.equals("isOldChunkAround")){output.visitCode();output.visitInsn(Opcodes.ICONST_0);output.visitInsn(Opcodes.IRETURN);output.visitMaxs(0,0);output.visitEnd();return null;}
     if((accessClass&&(method.equals("checkLock")||method.equals("saveDataTag")||method.equals("close")))||(saved&&(method.equals("save")||method.equals("saveAndJoin")))){output.visitCode();output.visitInsn(Opcodes.RETURN);output.visitMaxs(0,0);output.visitEnd();return null;}
     if((saved&&(method.equals("readSavedData")||method.equals("scheduleSave")))||(templates&&method.equals("loadFromGenerated"))||(storage&&(method.equals("read")||method.equals("write")))||(io&&(method.equals("store")||method.equals("loadAsync")||method.equals("scanChunk")||method.equals("synchronize")))){
      Type ret=Type.getReturnType(desc);output.visitCode();
      if(ret.getSort()==Type.VOID)output.visitInsn(Opcodes.RETURN);
      else if(ret.getClassName().equals("java.util.concurrent.CompletableFuture")){
       if((method.equals("read")||method.equals("loadAsync"))&&signature!=null&&signature.contains("java/util/Optional"))output.visitMethodInsn(Opcodes.INVOKESTATIC,"java/util/Optional","empty","()Ljava/util/Optional;",false);else output.visitInsn(Opcodes.ACONST_NULL);
       output.visitMethodInsn(Opcodes.INVOKESTATIC,"java/util/concurrent/CompletableFuture","completedFuture","(Ljava/lang/Object;)Ljava/util/concurrent/CompletableFuture;",false);output.visitInsn(Opcodes.ARETURN);
      }else if(ret.getClassName().equals("java.util.Optional")){output.visitMethodInsn(Opcodes.INVOKESTATIC,"java/util/Optional","empty","()Ljava/util/Optional;",false);output.visitInsn(Opcodes.ARETURN);}
      else{output.visitInsn(Opcodes.ACONST_NULL);output.visitInsn(Opcodes.ARETURN);}
      output.visitMaxs(0,0);output.visitEnd();return null;
     }
     return new MethodVisitor(Opcodes.ASM9,output){
      public void visitCode(){super.visitCode();
       if(name.endsWith("/PlacedFeature")&&method.equals("placeWithBiomeCheck")&&desc.endsWith(")Z")&&(access&Opcodes.ACC_STATIC)==0){
        Label normal=new Label();super.visitMethodInsn(Opcodes.INVOKESTATIC,"VersionQueryRuntime","skipPostHutFeature","()Z",false);super.visitJumpInsn(Opcodes.IFEQ,normal);super.visitInsn(Opcodes.ICONST_0);super.visitInsn(Opcodes.IRETURN);super.visitLabel(normal);super.visitFrame(Opcodes.F_SAME,0,null,0,null);
       }
       if(sectionWrite){super.visitVarInsn(Opcodes.ALOAD,0);super.visitMethodInsn(Opcodes.INVOKESTATIC,"VersionQueryRuntime","beforeSectionWrite","(Ljava/lang/Object;)V",false);}
       if(name.endsWith("/ChunkGenerator")&&method.equals("applyBiomeDecoration")){super.visitVarInsn(Opcodes.ALOAD,2);super.visitMethodInsn(Opcodes.INVOKESTATIC,"VersionQueryObservation","feature","(Ljava/lang/Object;)V",false);}if(name.endsWith("/GenerationChunkHolder")&&(method.equals("increaseGenerationRefCount")||method.equals("decreaseGenerationRefCount")))super.visitMethodInsn(Opcodes.INVOKESTATIC,"VersionQueryRuntime",method.startsWith("increase")?"claim":"release","()V",false);if(height){super.visitVarInsn(Opcodes.ALOAD,0);super.visitMethodInsn(Opcodes.INVOKESTATIC,"VersionQueryObservation","begin","(Ljava/lang/Object;)V",false);}if(stage){super.visitVarInsn(Opcodes.ALOAD,0);super.visitMethodInsn(Opcodes.INVOKESTATIC,"VersionQueryRuntime","stageBegin","(Ljava/lang/Object;)V",false);}}
      public void visitFieldInsn(int opcode,String owner,String field,String descriptor){super.visitFieldInsn(opcode,owner,field,descriptor);if(opcode==Opcodes.GETFIELD&&name.endsWith("/TracingExecutor")&&descriptor.equals("Ljava/util/concurrent/ExecutorService;"))super.visitMethodInsn(Opcodes.INVOKESTATIC,"VersionQueryRuntime","executor","(Ljava/util/concurrent/ExecutorService;)Ljava/util/concurrent/ExecutorService;",false);}
      public void visitMethodInsn(int opcode,String owner,String called,String descriptor,boolean iface){
       // No world directory is created. Jar/resource reads retain their ordinary paths.
       if((name.endsWith("/ServerChunkCache")||name.endsWith("/PlayerDataStorage"))&&owner.equals("java/io/File")&&called.equals("mkdirs")&&descriptor.equals("()Z")){super.visitInsn(Opcodes.POP);super.visitInsn(Opcodes.ICONST_0);return;}
       if(name.endsWith("/ServerChunkCache")&&owner.endsWith("/FileUtil")&&called.equals("createDirectoriesSafe")&&descriptor.equals("(Ljava/nio/file/Path;)V")){super.visitInsn(Opcodes.POP);return;}
       super.visitMethodInsn(opcode,owner,called,descriptor,iface);
       if(height&&called.equals("getHeightmapPos")){super.visitMethodInsn(Opcodes.INVOKESTATIC,"VersionQueryObservation","sample","(Ljava/lang/Object;)Ljava/lang/Object;",false);super.visitTypeInsn(Opcodes.CHECKCAST,Type.getReturnType(descriptor).getInternalName());}
      }
      public void visitInsn(int opcode){
       if(height&&opcode==Opcodes.IRETURN)super.visitMethodInsn(Opcodes.INVOKESTATIC,"VersionQueryObservation","end","()V",false);
       if(opcode==Opcodes.ARETURN&&stage){super.visitMethodInsn(Opcodes.INVOKESTATIC,"VersionQueryRuntime","stage","(Ljava/lang/Object;)Ljava/lang/Object;",false);super.visitTypeInsn(Opcodes.CHECKCAST,"java/util/concurrent/CompletableFuture");}
       if(opcode==Opcodes.ARETURN&&(name.equals("net/minecraft/Util")||name.equals("net/minecraft/util/Util"))&&(method.equals("backgroundExecutor")||method.equals("ioPool"))&&Type.getReturnType(desc).getClassName().equals("java.util.concurrent.ExecutorService"))super.visitMethodInsn(Opcodes.INVOKESTATIC,"VersionQueryRuntime","executor","(Ljava/util/concurrent/ExecutorService;)Ljava/util/concurrent/ExecutorService;",false);
       super.visitInsn(opcode);
      }
     };
    }
   },0);return writer.toByteArray();
  }});
 }
}
