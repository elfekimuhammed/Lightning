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

// 04b: the probe runs the shared encrypted round-trip, so it carries Lightning's own package and the committed
// dummy fixture (as package `roundtrip_fixture`, read with pkgutil). Copied at configuration, so every build
// uses the checked-out sources.
val sharedPython = layout.buildDirectory.dir("shared-python").get().asFile
sync {
    from("../../lightning") { into("lightning"); exclude("**/__pycache__/**") }
    from("../../tests/fixtures/roundtrip") { into("roundtrip_fixture") }
    into(sharedPython)
}
file("$sharedPython/roundtrip_fixture/__init__.py").writeText("")

chaquopy {
    sourceSets {
        getByName("main") { srcDir(sharedPython) }
    }
    defaultConfig {
        version = "3.13"
        extractPackages("lightning")  // migrations, seed files and the catalogue are read from disk
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
            // Native dependencies the index lacks (cffi >= 2.0, pydantic-core) come from the same run.
            wheels.filter { (it.name.startsWith("cffi-") || it.name.startsWith("pydantic_core-")) && it.name.endsWith(".whl") }.forEach { install(it.absolutePath) }
            install("fastapi==0.141.1")
            install("uvicorn==0.54.0")
            install("jinja2==3.1.6")
            install("python-multipart==0.0.32")
            install("tzdata==2026.2")
        }
    }
}
