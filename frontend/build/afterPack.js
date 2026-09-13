// electron-builder afterPack hook (macOS only).
//
// We ship without an Apple Developer certificate, so electron-builder skips
// signing ("identity": null). Apple Silicon refuses to launch *completely*
// unsigned Mach-O binaries, so we ad-hoc sign the whole bundle (identity "-")
// here — that is enough for the app to run once the user clears the
// quarantine flag (right-click → Open, or `xattr -cr /Applications/LocWarp.app`).
//
// The PyInstaller backend lives in Contents/Resources/backend; make sure its
// launcher keeps the executable bit and gets covered by the ad-hoc signature.
const { execSync } = require('child_process')
const fs = require('fs')
const path = require('path')

exports.default = async function afterPack(context) {
  if (context.electronPlatformName !== 'darwin') return

  const appName = context.packager.appInfo.productFilename
  const appPath = path.join(context.appOutDir, `${appName}.app`)
  const backendDir = path.join(appPath, 'Contents', 'Resources', 'backend')
  const backendExe = path.join(backendDir, 'locwarp-backend')

  if (fs.existsSync(backendExe)) {
    fs.chmodSync(backendExe, 0o755)
    // Ad-hoc sign every Mach-O inside the backend folder first (nested code
    // in Resources is not covered by `codesign --deep`).
    try {
      execSync(
        `find "${backendDir}" -type f \\( -name "*.so" -o -name "*.dylib" -o -perm -u+x \\) ` +
        `-exec sh -c 'file -b "$1" | grep -q Mach-O && codesign --force --sign - "$1"' _ {} \\;`,
        { stdio: 'inherit' },
      )
    } catch (e) {
      console.warn('[afterPack] backend ad-hoc signing had errors (continuing):', e.message)
    }
  } else {
    console.warn('[afterPack] backend executable not found at', backendExe)
  }

  execSync(`codesign --force --deep --sign - "${appPath}"`, { stdio: 'inherit' })
  execSync(`codesign --verify --deep --strict "${appPath}"`, { stdio: 'inherit' })
  console.log('[afterPack] ad-hoc signed', appPath)
}
