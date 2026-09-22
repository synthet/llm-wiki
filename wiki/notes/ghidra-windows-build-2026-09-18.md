# Ghidra Windows source build — workstation notes (2026-09-18)

Local notes from building NSA Ghidra on this Windows workstation. Treat as internal evidence.

## Checkout

- Workspace path: `D:\Projects\ghidra`
- Source: shallow clone of `https://github.com/NationalSecurityAgency/ghidra.git` into that directory

## Tooling requirements observed from master

- `Ghidra/application.properties` on master declares `application.version=12.3`, `application.release.name=DEV`, `application.java.min=25`, `application.java.compiler=25`, and `application.gradle.min=9.1`
- Upstream README Build section requires JDK 25 64-bit, Gradle 9.1.0+ (or the Gradle wrapper), Python 3.9–3.14, and on Windows Visual Studio 2017+ or Microsoft C++ Build Tools with MSVC, Windows SDK, and C++ ATL

## Dependency fetch and build commands

- Fetch non-Maven dependencies: `gradlew.bat -I gradle/support/fetchDependencies.gradle`
- Create development build: `gradlew.bat buildGhidra`
- Compressed development build output directory: `build/dist/`

## Workstation outcomes (2026-09-18)

- Portable Temurin JDK 25 was used at `C:\Users\dmnsy\.jdks\jdk-25.0.4+7`
- `fetchDependencies` completed successfully
- First `buildGhidra` failed on `:PDB:win_x86_64PDBMake` because `atlcomcli.h` was missing (C++ ATL not installed in Visual Studio Build Tools 2022)
- After installing `Microsoft.VisualStudio.Component.VC.ATLMFC` into Build Tools, `pdb.exe` built and a full distribution zip was produced at `D:\Projects\ghidra\build\dist\ghidra_12.3_DEV_20260918.zip`
