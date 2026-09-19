package com.termux.app;

import android.content.Context;
import android.system.ErrnoException;
import android.system.Os;
import android.system.OsConstants;

import com.termux.shared.logger.Logger;
import com.termux.shared.termux.TermuxConstants;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;

/** Experimental, ARM64-only compatibility runtime enabled by the prototype build. */
final class BundledAetherInstaller {
    private BundledAetherInstaller() {}

    static synchronized void install(Context context) {
        File helper = new File(context.getApplicationInfo().nativeLibraryDir, "libaether-run.so");
        if (!helper.isFile()) return;
        File runtime = new File(context.getFilesDir(), "aether");
        try {
            if (!runtime.isDirectory() && !runtime.mkdirs()) throw new IOException("Cannot create " + runtime);
            for (String name : context.getAssets().list("aether")) {
                try (InputStream input = context.getAssets().open("aether/" + name)) {
                    ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                    byte[] buffer = new byte[8192];
                    int count;
                    while ((count = input.read(buffer)) != -1) bytes.write(buffer, 0, count);
                    BundledRishInstaller.installFile(new File(runtime, name), bytes.toByteArray(), false);
                }
            }
            String script = "#!/system/bin/sh\nexport AETHER_RUNTIME='" + runtime.getAbsolutePath()
                + "'\nexport AETHER_RESOLV_CONF='" + TermuxConstants.TERMUX_PREFIX_DIR_PATH
                + "/etc/resolv.conf'\nexec '" + helper.getAbsolutePath() + "' \"$@\"\n";
            BundledRishInstaller.installFile(new File(runtime, "aether-run"),
                script.getBytes(StandardCharsets.UTF_8), true);
            try {
                Os.symlink(new File(runtime, "aether-run").getAbsolutePath(),
                    new File(TermuxConstants.TERMUX_PREFIX_DIR, "bin/aether-run").getAbsolutePath());
            } catch (ErrnoException e) {
                if (e.errno != OsConstants.EEXIST) throw e;
            }
        } catch (IOException | ErrnoException e) {
            Logger.logError("BundledAetherInstaller", "Cannot install prototype runtime: " + e.getMessage());
        }
    }
}
