plugins {
    id("com.android.application")
    id("com.chaquo.python")
}

android {
    namespace = "org.lightning.probe"
    compileSdk = 35

    defaultConfig {
        applicationId = "org.lightning.probe"
        minSdk = 24
        targetSdk = 35
        versionCode = 1
        versionName = "0.1"
        ndk {
            abiFilters += "arm64-v8a"
        }
    }
}

chaquopy {
    defaultConfig {
        version = "3.13"
        pip {
            // CI resolves cryptography alone too, so SQLCipher's missing wheel
            // cannot conceal a second independent native-package failure.
            // -PwheelDir: the arm64 wheels built by android-native-wheels.yml, since Chaquopy's index
            // has neither pinned version. Without it, the pinned names (which do not resolve today).
            val wheels = providers.gradleProperty("wheelDir").orNull?.let { file(it).listFiles()?.toList() } ?: emptyList()
            fun pinned(name: String, spec: String) =
                install(wheels.firstOrNull { it.name.startsWith(name + "-") && it.name.endsWith(".whl") }?.absolutePath ?: spec)
            if (providers.gradleProperty("probeMode").orElse("full").get() != "crypto-only") {
                pinned("sqlcipher3", "sqlcipher3==0.6.2")
            }
            pinned("cryptography", "cryptography==50.0.2")
            install("fastapi==0.141.1")
            install("uvicorn==0.54.0")
            install("jinja2==3.1.6")
            install("python-multipart==0.0.32")
            install("tzdata==2026.2")
        }
    }
}
