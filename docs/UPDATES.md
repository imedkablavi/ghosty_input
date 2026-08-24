# Ghosty Input update system

Ghosty Input checks the project's official GitHub Releases for newer packaged builds. The camera/input runtime remains local; update checks are the only network activity added by the updater.

## User behavior

Packaged builds check for updates at startup when `auto_check_updates` is enabled. Automatic checks are rate-limited to one attempt every six hours so repeated application launches do not repeatedly contact GitHub or consume the public API allowance.

The default update channel is `auto`:

- an Alpha build accepts newer Alpha releases and stable releases;
- a stable build accepts stable releases only;
- `stable` forces stable-only updates;
- `alpha` accepts prereleases and stable releases.

When an update is found, Ghosty Input asks before downloading or installing it. It does not silently replace the application.

CLI controls:

```bash
ghosty-input --check-update
ghosty-input --check-update --update-channel stable
ghosty-input --update

ghosty-input --set-update-channel auto
ghosty-input --set-update-channel stable
ghosty-input --set-update-channel alpha
ghosty-input --enable-auto-update-check
ghosty-input --disable-auto-update-check
```

Manual `--check-update` and `--update` commands bypass the six-hour startup cooldown. Source checkouts can check for releases but are not overwritten automatically.

## Integrity and trust boundary

The updater:

1. reads published releases only from `imedkablavi/ghosty_input`;
2. accepts download URLs only from that repository's GitHub Release path;
3. chooses the package type that matches the current installation;
4. downloads the platform checksum file;
5. verifies the package with SHA-256 before launching any installer;
6. rejects packages above the configured size ceiling;
7. validates portable Linux tar paths and special files before self-update.

If checksum verification fails, the downloaded package is deleted and installation is blocked.

## Platform behavior

### Linux `.deb`

A build running from `/opt/ghosty-input` selects the Debian package. After SHA-256 verification, Ghosty Input uses PolicyKit (`pkexec`) to run `apt-get install` so the desktop user receives a normal privilege prompt. Ghosty Input itself is never run as root.

### Linux portable

A portable build selects the Linux `.tar.gz`. A temporary helper waits for the current process to exit, extracts the verified archive, swaps the application directory, starts the new binary, and keeps a rollback copy during the replacement operation.

### Windows

The packaged Windows build selects `GhostyInputSetup.exe`, verifies it, launches the Inno Setup installer, and exits so the installer can replace the application files cleanly.

## Publishing an update

A code commit alone is not treated as an installable update. This is intentional: users must never auto-install an untested branch or arbitrary `main` snapshot.

To publish a real update:

1. bump the application/package version in the repository;
2. pass CI and distribution gates;
3. create a `v*` Git tag pointing at the accepted commit, for example:

```bash
git tag v0.6.0a2
git push origin v0.6.0a2
```

The Linux and Windows distribution workflows build the tag. After each successful tagged build, **Publish Release Assets** creates or updates the matching GitHub Release and uploads the platform packages, SHA-256 files, and build manifests.

The client ignores a newly created release until the package and matching checksum for its platform are both present, so Linux and Windows builds may finish in either order safely.

## Release gates

The distribution CI checks that the updater imports inside packaged binaries. Linux additionally validates that the generated portable archive is accepted by the same archive-safety logic used by the self-updater.

Do not mark a release stable until hardware acceptance for the target camera/compositor combinations has passed.
