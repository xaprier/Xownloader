allprojects {
    repositories {
        google()
        mavenCentral()
    }
}

val newBuildDir: Directory =
    rootProject.layout.buildDirectory
        .dir("../../build")
        .get()
rootProject.layout.buildDirectory.value(newBuildDir)

subprojects {
    val newSubprojectBuildDir: Directory = newBuildDir.dir(project.name)
    project.layout.buildDirectory.value(newSubprojectBuildDir)
}
subprojects {
    // Some plugins (e.g. receive_sharing_intent 1.9.0) declare a bleeding-edge
    // compileSdk that has no stable Android platform yet. Clamp any plugin
    // module back to the SDK the app itself is built against.
    afterEvaluate {
        (extensions.findByName("android") as? com.android.build.gradle.LibraryExtension)?.let { ext ->
            val appCompileSdk = 36
            if ((ext.compileSdk ?: 0) > appCompileSdk) {
                ext.compileSdk = appCompileSdk
            }
        }
    }
    project.evaluationDependsOn(":app")
}

tasks.register<Delete>("clean") {
    delete(rootProject.layout.buildDirectory)
}
