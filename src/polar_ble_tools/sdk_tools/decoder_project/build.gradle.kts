plugins {
    application
    kotlin("jvm") version "2.3.20"
}

repositories {
    google()
    mavenCentral()
}

val sdkSource = providers.gradleProperty("polarSdkSource")
    .orElse(providers.environmentVariable("POLAR_SDK_SOURCE"))
    .orNull
    ?.let(::file)
    ?.takeIf(File::isDirectory)
    ?: error("Set -PpolarSdkSource to the cached SDK library/src/main/java directory.")

kotlin {
    jvmToolchain(21)
    sourceSets {
        named("main") {
            kotlin.setSrcDirs(listOf(layout.projectDirectory.dir("src/main/kotlin"), sdkSource))
            kotlin.setIncludes(
                listOf(
                    "DecoderMain.kt",
                    "com/polar/androidcommunications/api/ble/BleLogger.kt",
                    "com/polar/androidcommunications/api/ble/exceptions/*.kt",
                    "com/polar/androidcommunications/api/ble/model/gatt/BleGattBase.kt",
                    "com/polar/androidcommunications/api/ble/model/gatt/BleGattTxInterface.kt",
                    "com/polar/androidcommunications/api/ble/model/gatt/client/pmd/*.kt",
                    "com/polar/androidcommunications/api/ble/model/gatt/client/pmd/errors/*.kt",
                    "com/polar/androidcommunications/api/ble/model/gatt/client/pmd/model/*.kt",
                    "com/polar/androidcommunications/api/ble/model/offlinerecording/*.kt",
                    "com/polar/androidcommunications/common/ble/AtomicSet.kt",
                    "com/polar/androidcommunications/common/ble/BleUtils.kt",
                    "com/polar/androidcommunications/common/ble/ChannelUtils.kt",
                    "com/polar/androidcommunications/common/ble/TypeUtils.kt",
                )
            )
        }
    }
}

dependencies {
    implementation(kotlin("reflect"))
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.10.2")
    implementation("androidx.annotation:annotation:1.6.0")
}

application {
    mainClass = "DecoderMainKt"
    applicationName = "polar-rec-decoder"
}
