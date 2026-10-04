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
            if (providers.gradleProperty("probeMode").orElse("full").get() != "crypto-only") {
                install("sqlcipher3==0.6.2")
            }
            install("cryptography==50.0.2")
            install("fastapi==0.141.1")
            install("uvicorn==0.54.0")
            install("jinja2==3.1.6")
            install("python-multipart==0.0.32")
            install("tzdata==2026.2")
        }
    }
}
