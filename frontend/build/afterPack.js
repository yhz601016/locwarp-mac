// electron-builder afterPack hook (macOS only).
//
// We ship without an Apple Developer certificate, so electron-builder skips
// signing ("identity": null). Apple Silicon refuses to launch *completely*
// unsigned Mach-O binaries, so we ad-hoc sign the app bundle (identity "-")
// here — that is enough for the app to run once the user clears the
// quarantine flag (right-click → Open, or `xattr -cr`).
//
// IMPORTANT: do NOT re-sign anything under Contents/Resources/backend.
// PyInstaller already ad-hoc signs its bootloader and every collected
// .so/.dylib at build time, and the bootloader carries the Python module
// archive appended to the Mach-O. Running `codesign --force` on it again
// rewrites the binary layout and corrupts that archive: early imports still
// work, later ones die with "zlib.error: unknown compression method"
// (v0.3.3 shipped exactly that bug). `codesign --deep` on the .app treats
// Resources as data and leaves those files alone.
const { execSync } = require('child_process')
const fs = require('fs')
const path = require('path')

exports.default = async function afterPack(context) {
  if (context.electronPlatformName !== 'darwin') return

  const appName = context.packager.appInfo.productFilename
  const appPath = path.join(context.appOutDir, `${appName}.app`)
  const backendExe = path.join(appPath, 'Contents', 'Resources', 'backend', 'locwarp-backend')

  if (fs.existsSync(backendExe)) {
    fs.chmodSync(backendExe, 0o755)
    // Sanity: PyInstaller's own ad-hoc signature must still be valid.
    execSync(`codesign --verify --verbose=1 "${backendExe}"`, { stdio: 'inherit' })
  } else {
    console.warn('[afterPack] backend executable not found at', backendExe)
  }

  execSync(`codesign --force --deep --sign - "${appPath}"`, { stdio: 'inherit' })
  execSync(`codesign --verify --deep --strict "${appPath}"`, { stdio: 'inherit' })
  console.log('[afterPack] ad-hoc signed', appPath)
}
