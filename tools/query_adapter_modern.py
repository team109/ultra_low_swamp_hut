"""Compile-time hosting adapters for the pinned vanilla generation JARs."""

import re


def adapt_query_source(source, version):
    version_parts = tuple(map(int, version.split(".")))
    adapted_source = source
    if version_parts < (1, 21):
        adapted_source = adapted_source.replace(
            "net.minecraft.resources.ResourceLocation.parse(forced)",
            "new net.minecraft.resources.ResourceLocation(forced)",
        )
    if version_parts < (1, 20, 6):
        adapted_source = adapted_source.replace(
            "import net.minecraft.world.level.chunk.status.*;", ""
        )
        adapted_source = adapted_source.replace(
            "import net.minecraft.util.debugchart.*;", ""
        )
        adapted_source = adapted_source.replace(
            "final LocalSampleLogger samples=new LocalSampleLogger(4);", ""
        )
        adapted_source = re.sub(
            r"  @Override protected SampleLogger getTickTimeLogger\(\)\{return samples;\}\n",
            "",
            adapted_source,
        )
        adapted_source = re.sub(
            r"  @Override public boolean isTickTimeLoggingEnabled\(\)\{return false;\}\n",
            "",
            adapted_source,
        )
        adapted_source = adapted_source.replace(
            '((ChunkResult<ChunkAccess>)future.join()).orElseThrow(()->new IllegalStateException("Chunk unavailable"))',
            "((com.mojang.datafixers.util.Either<ChunkAccess,?>)future.join()).left().orElseThrow()",
        )
    if version_parts < (1, 20, 2):
        adapted_source = adapted_source.replace(
            "ServerPacksSource.createVanillaTrustedRepository()",
            "new PackRepository(new ServerPacksSource())",
        )
        adapted_source = adapted_source.replace(
            "await(source.getLightEngine().waitForPendingTasks(x,z));", ""
        )
    if version_parts < (1, 20):
        adapted_source = adapted_source.replace(
            "List.of(),true,null);", "List.of(),true);"
        )
        adapted_source = adapted_source.replace(
            "auth.getServicesKeySet()",
            "net.minecraft.util.SignatureValidator.from(auth.getServicesKey())",
        )
    if version_parts >= (1, 21, 2):
        adapted_source = adapted_source.replace(
            "new GameRules()",
            "new GameRules(context.dataConfiguration().enabledFeatures())",
        )
        adapted_source = adapted_source.replace(".registryOrThrow(", ".lookupOrThrow(")
        adapted_source = adapted_source.replace(
            ".getOrThrow(LevelStem.OVERWORLD)", ".getValueOrThrow(LevelStem.OVERWORLD)"
        )
        adapted_source = adapted_source.replace(".getHolderOrThrow(", ".getOrThrow(")
        adapted_source = adapted_source.replace(
            "chunk.getMinBuildHeight()", "chunk.getMinY()"
        ).replace("chunk.getMaxBuildHeight()", "chunk.getMaxY()+1")
    if version_parts >= (1, 21, 9):
        adapted_source = adapted_source.replace(
            "services=new Services(auth.createMinecraftSessionService(),auth.getServicesKeySet(),auth.createProfileRepository(),null);",
            'services=Services.create(auth,Path.of("__vanilla_query_memory__").toFile());',
        )
        adapted_source = re.sub(
            r" static final ChunkProgressListener PROGRESS=.*?;\n",
            " static final LevelLoadListener PROGRESS=LoggingLevelLoadListener.forDedicatedServer();\n",
            adapted_source,
        )
        adapted_source = adapted_source.replace(
            "services,radius->PROGRESS);", "services,PROGRESS);"
        )
        adapted_source = adapted_source.replace(
            "playerDataStorage,0){}", "playerDataStorage,notificationManager()){}"
        )
        adapted_source = adapted_source.replace(
            "dimension,PROGRESS,false", "dimension,false"
        )
        adapted_source = adapted_source.replace(
            "getOperatorUserPermissionLevel()", "operatorUserPermissionLevel()"
        )
        adapted_source = adapted_source.replace(
            "isSingleplayerOwner(GameProfile p)",
            "isSingleplayerOwner(net.minecraft.server.players.NameAndId p)",
        )
        adapted_source = adapted_source.replace(
            "  @Override public boolean isCommandBlockEnabled(){return false;}",
            "  @Override public int getMaxPlayers(){return 0;}",
        )
    if version_parts >= (1, 21, 11):
        adapted_source = adapted_source.replace(
            "import net.minecraft.Util;",
            "import net.minecraft.util.Util;\nimport net.minecraft.world.level.gamerules.GameRules;\nimport net.minecraft.server.permissions.*;",
        )
        adapted_source = adapted_source.replace(
            "Commands.CommandSelection.DEDICATED,2)",
            "Commands.CommandSelection.DEDICATED,LevelBasedPermissionSet.OWNER)",
        )
        adapted_source = adapted_source.replace(
            "@Override public int operatorUserPermissionLevel(){return 4;}",
            "@Override public LevelBasedPermissionSet operatorUserPermissions(){return LevelBasedPermissionSet.OWNER;}",
        )
        adapted_source = adapted_source.replace(
            "@Override public int getFunctionCompilationLevel(){return 2;}",
            "@Override public PermissionSet getFunctionCompilationPermissions(){return LevelBasedPermissionSet.OWNER;}",
        )
        adapted_source = adapted_source.replace(
            "isEpollEnabled()", "useNativeTransport()"
        )
        adapted_source = adapted_source.replace(
            "net.minecraft.resources.ResourceLocation",
            "net.minecraft.resources.Identifier",
        )
        adapted_source = adapted_source.replace(
            'invokeMethod(this,"readScoreboard",level.getDataStorage());',
            'getScoreboard().load(level.getDataStorage().computeIfAbsent(net.minecraft.world.scores.ScoreboardSaveData.TYPE).getData());writeField(this,"stopwatches",level.getDataStorage().computeIfAbsent(net.minecraft.world.Stopwatches.TYPE));',
        )
    if version_parts >= (26, 1):
        adapted_source = adapted_source.replace(
            "import com.mojang.authlib.yggdrasil.YggdrasilAuthenticationService;",
            "import com.mojang.authlib.services.MinecraftServicesDiscoveryService;",
        )
        adapted_source = adapted_source.replace(
            "new YggdrasilAuthenticationService(Proxy.NO_PROXY)",
            "MinecraftServicesDiscoveryService.create(Proxy.NO_PROXY)",
        )
        adapted_source = adapted_source.replace(
            "net.minecraft.resources.ResourceLocation",
            "net.minecraft.resources.Identifier",
        )
        adapted_source = adapted_source.replace(
            "ChunkPos.asLong(x,z)", "ChunkPos.pack(x,z)"
        )
        adapted_source = adapted_source.replace(
            "static WorldStem stem;static PackRepository packs;",
            "static WorldStem stem;static PackRepository packs;static WorldDimensions dimensions;",
        )
        a = adapted_source.index("   var settings=new LevelSettings(")
        b = adapted_source.index("\n  },WorldStem::new", a)
        adapted_source = (
            adapted_source[:a]
            + """   dimensions=WorldPresets.createNormalWorldDimensions(context.datapackWorldRegistries());
   var complete=dimensions.bake(new net.minecraft.core.MappedRegistry<LevelStem>(Registries.LEVEL_STEM,com.mojang.serialization.Lifecycle.stable()).freeze());
   var settings=new LevelSettings("query",GameType.SURVIVAL,LevelSettings.DifficultySettings.DEFAULT,false,context.dataConfiguration());
   var data=new PrimaryLevelData(settings,complete.specialWorldProperty(),complete.lifecycle());
   return new WorldLoader.DataLoadOutput<>(new LevelDataAndDimensions.WorldDataAndGenSettings(data,new WorldGenSettings(new WorldOptions(0,true,false),dimensions)),complete.dimensionsRegistryAccess());"""
            + adapted_source[b:]
        )
        adapted_source = adapted_source.replace(
            "storage,packs,state,Proxy.NO_PROXY",
            "storage,packs,state,Optional.empty(),Proxy.NO_PROXY",
        )
        adapted_source = adapted_source.replace(
            "services,PROGRESS);",
            "services,PROGRESS,false"
            + (
                ",new net.minecraft.server.notifications.NotificationManager()"
                if version_parts >= (26, 2)
                else ""
            )
            + ");",
        )
        adapted_source = adapted_source.replace(
            "getWorldData().worldGenOptions().seed()",
            "getWorldGenSettings().options().seed()",
        )
        adapted_source = adapted_source.replace(
            "List.of(),true,null);", "List.of(),true);"
        )
        adapted_source = adapted_source.replace(
            "stem.worldData()", "stem.worldDataAndGenSettings().data()"
        )
        adapted_source = adapted_source.replace(
            'new PrimaryLevelData((LevelSettings)readField(base,"settings"),new WorldOptions(seed,true,false),PrimaryLevelData.SpecialWorldProperty.NONE,com.mojang.serialization.Lifecycle.stable())',
            'new PrimaryLevelData((LevelSettings)readField(base,"settings"),PrimaryLevelData.SpecialWorldProperty.NONE,com.mojang.serialization.Lifecycle.stable())',
        )
        adapted_source = adapted_source.replace(
            "stem.registries(),data);",
            "stem.registries(),new LevelDataAndDimensions.WorldDataAndGenSettings(data,new WorldGenSettings(new WorldOptions(seed,true,false),dimensions)));",
        )
        adapted_source = adapted_source.replace(
            'invokeMethod(this,"readScoreboard",level.getDataStorage());',
            'getScoreboard().load(getDataStorage().computeIfAbsent(net.minecraft.world.scores.ScoreboardSaveData.TYPE).getData());writeField(this,"stopwatches",getDataStorage().computeIfAbsent(net.minecraft.world.Stopwatches.TYPE));',
        )
        adapted_source = adapted_source.replace(
            "@Override public int getMaxPlayers(){return 0;}",
            "@Override public int getMaxPlayers(){return 0;}\n  @Override public int getCommandSpamThresholdSeconds(){return 0;}\n  @Override public int getChatSpamThresholdSeconds(){return 0;}",
        )
        if version_parts < (26, 3):
            adapted_source = adapted_source.replace(
                "import com.mojang.authlib.services.MinecraftServicesDiscoveryService;",
                "import com.mojang.authlib.yggdrasil.YggdrasilAuthenticationService;",
            )
            adapted_source = adapted_source.replace(
                "MinecraftServicesDiscoveryService.create(Proxy.NO_PROXY)",
                "new YggdrasilAuthenticationService(Proxy.NO_PROXY)",
            )
            adapted_source = adapted_source.replace(
                "context.datapackWorldRegistries()", "context.datapackWorldgen()"
            )
        if version_parts < (26, 2):
            adapted_source = adapted_source.replace(
                "  @Override public int getCommandSpamThresholdSeconds(){return 0;}\n",
                "",
            ).replace(
                "  @Override public int getChatSpamThresholdSeconds(){return 0;}\n", ""
            )
    return adapted_source
