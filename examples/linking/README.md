# Untitled

In a normal situation, when compiling an application, the dependencies must be
installed upfront and any install paths given to the application itself. With
Karsk you can build the application and all dependencies in the staging
catalogue and try it out, before considering installing it anywhere. Karsk
allows this because it builds in a container and the destination paths are
mounted. Hence all applications and dependencies believe they are in the correct
location.

This example showcases how it works. It builds a shared C library (`mathlib`)
and an application (`app`) that links against it.

## The key insight

During the build, `$mathlib` points to the **target** path (e.g.
`/opt/karsk/linking/store/<hash>-mathlib-1.0.0`). The C
compiler embeds this path into the binary via `-rpath`, so the application knows
where to find `libmath.so` at runtime.

This means:

- **In the staging folder**: running the `app` binary directly will fail because
  `libmath.so` is not at its expected target path.
- **With `karsk enter`**: the packages are mounted at their target paths, so the
  library is found and the application runs correctly.


