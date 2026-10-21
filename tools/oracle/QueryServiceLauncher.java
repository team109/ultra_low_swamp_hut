import java.io.InputStream;
import java.lang.reflect.InvocationTargetException;

/** Selects one hosting adapter while sharing the generation agent and runtime. */
public final class QueryServiceLauncher {
    private static final class AdapterLoader extends ClassLoader {
        private final String resourcePrefix;

        AdapterLoader(String version) {
            super(QueryServiceLauncher.class.getClassLoader());
            resourcePrefix = "adapters/" + version + "/";
        }

        @Override
        protected Class<?> loadClass(String name, boolean resolve) throws ClassNotFoundException {
            if (!name.equals("VanillaQueryMain") && !name.startsWith("VanillaQueryMain$")) {
                return super.loadClass(name, resolve);
            }
            synchronized (getClassLoadingLock(name)) {
                Class<?> loaded = findLoadedClass(name);
                if (loaded == null) loaded = findClass(name);
                if (resolve) resolveClass(loaded);
                return loaded;
            }
        }

        @Override
        protected Class<?> findClass(String name) throws ClassNotFoundException {
            String resource = resourcePrefix + name.replace('.', '/') + ".class";
            try (InputStream stream = getParent().getResourceAsStream(resource)) {
                if (stream == null) throw new ClassNotFoundException("Prepare query adapter for " + resourcePrefix);
                byte[] bytecode = stream.readAllBytes();
                return defineClass(name, bytecode, 0, bytecode.length);
            } catch (java.io.IOException failure) {
                throw new ClassNotFoundException(name, failure);
            }
        }
    }

    public static void main(String[] args) throws Throwable {
        String version = System.getProperty("hut.service.version");
        AdapterLoader loader = new AdapterLoader(version);
        Thread.currentThread().setContextClassLoader(loader);
        Class<?> entry = loader.loadClass("VanillaQueryMain");
        try {
            entry.getMethod("main", String[].class).invoke(null, (Object) args);
        } catch (InvocationTargetException failure) {
            throw failure.getCause();
        }
    }
}
