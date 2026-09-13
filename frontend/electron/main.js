const { app, BrowserWindow, Menu, shell, ipcMain, dialog } = require('electron')
const path = require('path')
const { spawn, execFile } = require('child_process')
const http = require('http')
const os = require('os')
const fs = require('fs')

const IS_MAC = process.platform === 'darwin'
const IS_WIN = process.platform === 'win32'

// ─────────────────────────────────────────────────────────────────────
// Render-mode preference (Windows 10 only; see upstream Issue #24).
// ─────────────────────────────────────────────────────────────────────
const RENDER_MODE_FILE = path.join(app.getPath('userData'), 'render-mode.json')

function readRenderModePref() {
  try {
    const raw = fs.readFileSync(RENDER_MODE_FILE, 'utf8')
    const parsed = JSON.parse(raw)
    if (parsed && (parsed.mode === 'hardware' || parsed.mode === 'software')) {
      return parsed.mode
    }
  } catch { /* missing or corrupt — fall through to default */ }
  return null
}

function writeRenderModePref(mode) {
  try {
    fs.mkdirSync(path.dirname(RENDER_MODE_FILE), { recursive: true })
    fs.writeFileSync(RENDER_MODE_FILE, JSON.stringify({ mode }, null, 2), 'utf8')
  } catch (e) {
    console.error('[render-mode] failed to save pref:', e && e.message)
  }
}

function isWin10() {
  if (!IS_WIN) return false
  const winBuild = parseInt((os.release() || '0.0.0').split('.')[2] || '0', 10)
  return winBuild > 0 && winBuild < 22000
}

if (IS_WIN) {
  const saved = readRenderModePref()
  const mode = saved || (isWin10() ? 'software' : 'hardware')
  if (mode === 'software') {
    app.disableHardwareAcceleration()
    app.commandLine.appendSwitch('no-sandbox')
    app.commandLine.appendSwitch('in-process-gpu')
  }
}

// ─────────────────────────────────────────────────────────────────────
// "Locate this computer" — used to centre the map on the user's real
// position. Three layers, best first:
//   Windows : PowerShell + System.Device.Location (Wi-Fi/GPS positioning)
//   macOS   : CoreLocationCLI if the user installed it (brew install corelocationcli)
//   any OS  : IP geolocation (≈ city level, no key needed)
// ─────────────────────────────────────────────────────────────────────
const LOCATE_PS_SCRIPT = `
$ErrorActionPreference = 'Stop'
try {
  Add-Type -AssemblyName System.Device
  $watcher = New-Object System.Device.Location.GeoCoordinateWatcher([System.Device.Location.GeoPositionAccuracy]::High)
  $watcher.Start()
  $deadline = (Get-Date).AddSeconds(15)
  while ((Get-Date) -lt $deadline) {
    if ($watcher.Permission -eq 'Denied') { Write-Output 'DENIED'; exit 0 }
    if ($watcher.Status -eq 'Ready' -and -not $watcher.Position.Location.IsUnknown) { break }
    Start-Sleep -Milliseconds 200
  }
  if ($watcher.Permission -eq 'Denied') { Write-Output 'DENIED'; exit 0 }
  $loc = $watcher.Position.Location
  if ($loc.IsUnknown) { Write-Output ('NODATA,status=' + $watcher.Status); exit 0 }
  Write-Output ('OK,' + $loc.Latitude + ',' + $loc.Longitude + ',' + $loc.HorizontalAccuracy)
  $watcher.Stop()
} catch {
  Write-Output ('ERROR,' + $_.Exception.Message)
}
`

const httpsGetJson = (url) => {
  return new Promise((resolve) => {
    const https = require('https')
    const req = https.get(url, { headers: { 'User-Agent': 'LocWarp-Mac-Electron' }, timeout: 6000 }, (res) => {
      if (res.statusCode !== 200) {
        res.resume()
        return resolve(null)
      }
      const chunks = []
      res.on('data', (c) => chunks.push(c))
      res.on('end', () => {
        try { resolve(JSON.parse(Buffer.concat(chunks).toString('utf8'))) }
        catch { resolve(null) }
      })
    })
    req.on('error', () => resolve(null))
    req.on('timeout', () => { try { req.destroy() } catch {} ; resolve(null) })
  })
}

const ipFallback = async () => {
  const a = await httpsGetJson('https://ipwho.is/')
  if (a && typeof a.latitude === 'number' && typeof a.longitude === 'number') {
    return { ok: true, lat: a.latitude, lng: a.longitude, accuracy: 5000, via: 'ipwho.is' }
  }
  const b = await httpsGetJson('https://ipapi.co/json/')
  if (b && b.latitude != null && b.longitude != null) {
    const lat = parseFloat(b.latitude); const lng = parseFloat(b.longitude)
    if (Number.isFinite(lat) && Number.isFinite(lng)) {
      return { ok: true, lat, lng, accuracy: 5000, via: 'ipapi.co' }
    }
  }
  const c = await httpsGetJson('https://freeipapi.com/api/json/')
  if (c && c.latitude != null && c.longitude != null) {
    const lat = parseFloat(c.latitude); const lng = parseFloat(c.longitude)
    if (Number.isFinite(lat) && Number.isFinite(lng)) {
      return { ok: true, lat, lng, accuracy: 5000, via: 'freeipapi.com' }
    }
  }
  return null
}

const tryWindowsLocation = () => {
  return new Promise((resolve) => {
    let settled = false
    const finish = (payload) => { if (!settled) { settled = true; resolve(payload) } }
    const child = spawn(
      'powershell.exe',
      ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-Command', LOCATE_PS_SCRIPT],
      { windowsHide: true },
    )
    let out = ''
    child.stdout.on('data', (d) => { out += d.toString('utf8') })
    child.stderr.on('data', (d) => console.error('[locate-pc] stderr:', d.toString('utf8')))
    child.on('error', (e) => finish({ ok: false, code: 'SPAWN_FAILED', message: e.message }))
    child.on('exit', () => {
      const trimmed = out.trim()
      if (trimmed.startsWith('OK,')) {
        const parts = trimmed.split(',')
        const lat = parseFloat(parts[1])
        const lng = parseFloat(parts[2])
        const acc = parseFloat(parts[3])
        if (Number.isFinite(lat) && Number.isFinite(lng)) {
          return finish({ ok: true, lat, lng, accuracy: Number.isFinite(acc) ? acc : 100 })
        }
      }
      if (trimmed === 'DENIED') return finish({ ok: false, code: 'DENIED', message: 'Windows Location service is off or app access denied' })
      if (trimmed.startsWith('NODATA')) return finish({ ok: false, code: 'NODATA', message: trimmed.slice(0, 200) })
      if (trimmed.startsWith('ERROR,')) return finish({ ok: false, code: 'ERROR', message: trimmed.slice(6, 200) })
      finish({ ok: false, code: 'UNKNOWN', message: trimmed.slice(0, 200) || 'no PowerShell output' })
    })
    setTimeout(() => {
      try { child.kill() } catch { /* ignore */ }
      finish({ ok: false, code: 'TIMEOUT', message: 'PowerShell timed out after 18s' })
    }, 18000)
  })
}

// macOS: CoreLocationCLI (https://github.com/fulldecent/corelocationcli) prints
// "lat lon" when installed. It is optional — most users will land on the IP
// fallback, which is plenty for centring a map.
const CORELOCATION_CLI_PATHS = [
  '/opt/homebrew/bin/CoreLocationCLI',
  '/usr/local/bin/CoreLocationCLI',
]

const tryCoreLocation = () => {
  return new Promise((resolve) => {
    const bin = CORELOCATION_CLI_PATHS.find((p) => { try { return fs.existsSync(p) } catch { return false } })
    if (!bin) return resolve({ ok: false, code: 'NODATA', message: 'CoreLocationCLI not installed' })
    execFile(bin, ['--once', '--format', '%latitude,%longitude,%h_accuracy'], { timeout: 15000 }, (err, stdout) => {
      if (err) {
        const msg = String(err.message || err)
        const denied = /denied|not authorized|kCLErrorDomain/i.test(msg)
        return resolve({ ok: false, code: denied ? 'DENIED' : 'ERROR', message: msg.slice(0, 200) })
      }
      const parts = String(stdout || '').trim().split(',')
      const lat = parseFloat(parts[0]); const lng = parseFloat(parts[1]); const acc = parseFloat(parts[2])
      if (Number.isFinite(lat) && Number.isFinite(lng)) {
        return resolve({ ok: true, lat, lng, accuracy: Number.isFinite(acc) ? acc : 100 })
      }
      resolve({ ok: false, code: 'NODATA', message: String(stdout || '').slice(0, 200) })
    })
  })
}

ipcMain.handle('get-render-mode', () => {
  const win10 = isWin10()
  const saved = readRenderModePref()
  const effective = saved || (win10 ? 'software' : 'hardware')
  return { mode: effective, saved, isWin10: win10 }
})

ipcMain.handle('set-render-mode', (_e, mode) => {
  if (mode !== 'hardware' && mode !== 'software') return { ok: false }
  writeRenderModePref(mode)
  return { ok: true }
})

ipcMain.handle('relaunch-app', () => {
  app.relaunch()
  app.exit(0)
})

ipcMain.handle('locate-pc', async () => {
  let native
  if (IS_WIN) {
    native = await tryWindowsLocation()
    if (native.ok) return { ...native, via: 'windows' }
  } else if (IS_MAC) {
    native = await tryCoreLocation()
    if (native.ok) return { ...native, via: 'corelocation' }
  } else {
    native = { ok: false, code: 'NODATA', message: 'no native location provider on this OS' }
  }
  if (native.code === 'DENIED') return native
  const ip = await ipFallback()
  if (ip) return ip
  return {
    ok: false,
    code: 'ALL_FAILED',
    message: `Native location: ${native.code}${native.message ? ' (' + native.message + ')' : ''} | IP fallback: all 3 services unreachable`,
  }
})

// ─────────────────────────────────────────────────────────────────────
// Application menu. Windows/Linux: none (the app has in-window controls).
// macOS: a minimal native menu is REQUIRED, otherwise ⌘Q / ⌘C / ⌘V / ⌘W
// stop working and the app cannot be quit from the Dock normally.
// ─────────────────────────────────────────────────────────────────────
if (IS_MAC) {
  Menu.setApplicationMenu(Menu.buildFromTemplate([
    {
      label: app.name,
      submenu: [
        { role: 'about' },
        { type: 'separator' },
        { role: 'hide' },
        { role: 'hideOthers' },
        { role: 'unhide' },
        { type: 'separator' },
        { role: 'quit' },
      ],
    },
    {
      label: 'Edit',
      submenu: [
        { role: 'undo' }, { role: 'redo' }, { type: 'separator' },
        { role: 'cut' }, { role: 'copy' }, { role: 'paste' }, { role: 'selectAll' },
      ],
    },
    {
      label: 'View',
      submenu: [
        { role: 'reload' }, { role: 'toggleDevTools' }, { type: 'separator' },
        { role: 'resetZoom' }, { role: 'zoomIn' }, { role: 'zoomOut' }, { type: 'separator' },
        { role: 'togglefullscreen' },
      ],
    },
    { role: 'window', submenu: [{ role: 'minimize' }, { role: 'zoom' }, { role: 'close' }] },
    {
      role: 'help',
      submenu: [
        { label: 'Open Log Folder', click: () => shell.openPath(path.join(os.homedir(), '.locwarp', 'logs')) },
        { label: 'GitHub', click: () => shell.openExternal('https://github.com/yhz601016/locwarp-mac') },
      ],
    },
  ]))
} else {
  Menu.setApplicationMenu(null)
}

let mainWindow = null
let backendProc = null

function resolveBackendExe() {
  // Packaged: extraResources places the PyInstaller folder under
  // <app>/Contents/Resources/backend (macOS) or resources/backend (Windows).
  // Dev: the developer runs `python3 backend/main.py` (or start.py) themselves.
  if (!app.isPackaged) return null
  const name = IS_WIN ? 'locwarp-backend.exe' : 'locwarp-backend'
  return path.join(process.resourcesPath, 'backend', name)
}

function showBackendMissingDialog(exe, detail) {
  const zh = (app.getLocale() || '').toLowerCase().startsWith('zh')
  let msg
  if (IS_MAC) {
    msg = zh
      ? {
          title: 'LocWarp 無法啟動',
          message: '背景服務 (locwarp-backend) 無法執行',
          detail:
            '最常見原因是 macOS Gatekeeper 的隔離屬性擋住了未公證的程式。\n\n' +
            '解決步驟：\n' +
            '1. 打開「終端機」，執行：\n' +
            '   xattr -cr /Applications/LocWarp.app\n' +
            '2. 重新開啟 LocWarp。\n\n' +
            '若仍失敗，請到 系統設定 → 隱私權與安全性 最下方按「仍要打開」。\n\n' +
            `預期路徑：\n${exe}` + (detail ? `\n\n${detail}` : ''),
          buttons: ['開啟程式資料夾', '關閉'],
        }
      : {
          title: 'LocWarp cannot start',
          message: 'Backend service (locwarp-backend) failed to launch',
          detail:
            'This is usually macOS Gatekeeper quarantining the unnotarized app.\n\n' +
            'How to fix:\n' +
            '1. Open Terminal and run:\n' +
            '   xattr -cr /Applications/LocWarp.app\n' +
            '2. Relaunch LocWarp.\n\n' +
            'If it still fails, open System Settings → Privacy & Security and click "Open Anyway".\n\n' +
            `Expected path:\n${exe}` + (detail ? `\n\n${detail}` : ''),
          buttons: ['Open app folder', 'Close'],
        }
  } else {
    msg = zh
      ? {
          title: 'LocWarp 無法啟動',
          message: '找不到背景服務 (locwarp-backend.exe)',
          detail:
            '這個檔案通常是被防毒軟體判定為可疑並隔離刪除。\n\n' +
            '解決步驟：\n' +
            '1. 到防毒軟體的防護歷程記錄還原 LocWarp 相關項目。\n' +
            '2. 把安裝資料夾加入排除清單。\n' +
            '3. 移除後重新安裝。\n\n' +
            `預期路徑：\n${exe}` + (detail ? `\n\n${detail}` : ''),
          buttons: ['開啟安裝資料夾', '關閉'],
        }
      : {
          title: 'LocWarp cannot start',
          message: 'Backend service not found (locwarp-backend.exe)',
          detail:
            'This file is usually removed by antivirus software.\n\n' +
            '1. Restore any LocWarp entry from the antivirus protection history.\n' +
            '2. Add the install folder to the exclusions.\n' +
            '3. Uninstall, then reinstall.\n\n' +
            `Expected path:\n${exe}` + (detail ? `\n\n${detail}` : ''),
          buttons: ['Open install folder', 'Close'],
        }
  }

  const choice = dialog.showMessageBoxSync({
    type: 'error',
    title: msg.title,
    message: msg.message,
    detail: msg.detail,
    buttons: msg.buttons,
    defaultId: 0,
    cancelId: 1,
    noLink: true,
  })
  if (choice === 0) {
    const dir = fs.existsSync(path.dirname(exe)) ? path.dirname(exe) : process.resourcesPath
    shell.openPath(dir)
  }
  app.quit()
}

function startBackend() {
  if (backendProc) return // already running (macOS re-activate after all windows closed)
  const exe = resolveBackendExe()
  if (!exe) return
  if (!fs.existsSync(exe)) {
    console.error('[electron] backend exe missing:', exe)
    showBackendMissingDialog(exe, null)
    return
  }
  if (!IS_WIN) {
    // The executable bit can get lost when the bundle is copied by a tool
    // that ignores modes (some zip extractors). Best-effort restore.
    try { fs.accessSync(exe, fs.constants.X_OK) } catch { try { fs.chmodSync(exe, 0o755) } catch {} }
  }
  console.log('[electron] spawning backend:', exe)
  try {
    backendProc = spawn(exe, [], {
      cwd: path.dirname(exe),
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true,
      env: {
        ...process.env,
        PYTHONUNBUFFERED: '1',
        // Userspace (no-root) tunnel on macOS unless the user overrides it.
        LOCWARP_TUNNEL_MODE: process.env.LOCWARP_TUNNEL_MODE || 'auto',
      },
    })
  } catch (e) {
    console.error('[electron] backend spawn threw:', e)
    showBackendMissingDialog(exe, String(e && e.message ? e.message : e))
    return
  }
  backendProc.on('error', (e) => {
    console.error('[electron] backend spawn error:', e)
    backendProc = null
    showBackendMissingDialog(exe, String(e && e.message ? e.message : e))
  })
  backendProc.stdout.on('data', (d) => process.stdout.write(`[backend] ${d}`))
  backendProc.stderr.on('data', (d) => process.stderr.write(`[backend] ${d}`))
  backendProc.on('exit', (code, signal) => {
    console.log('[electron] backend exited with code', code, 'signal', signal)
    backendProc = null
  })
}

function stopBackend() {
  if (!backendProc) return
  const proc = backendProc
  backendProc = null
  try { proc.kill('SIGTERM') } catch {}
  // uvicorn shuts down gracefully on SIGTERM; make sure it really goes away.
  setTimeout(() => { try { proc.kill('SIGKILL') } catch {} }, 3000)
}

function waitForBackend(timeoutMs = 30000) {
  const started = Date.now()
  return new Promise((resolve, reject) => {
    const tick = () => {
      const req = http.get('http://127.0.0.1:8777/docs', (res) => {
        res.destroy()
        resolve()
      })
      req.on('error', () => {
        if (Date.now() - started > timeoutMs) return reject(new Error('backend timeout'))
        setTimeout(tick, 500)
      })
    }
    tick()
  })
}

async function createWindow() {
  // OSM tile policy requires an identifying User-Agent; Electron's default
  // Chrome UA gets HTTP 418. Rewrite the UA on requests to the OSM tile hosts.
  try {
    const { session } = require('electron')
    const OSM_HOSTS = [
      'tile.openstreetmap.org',
      'a.tile.openstreetmap.org',
      'b.tile.openstreetmap.org',
      'c.tile.openstreetmap.org',
      'tile.openstreetmap.fr',
      'a.tile.openstreetmap.fr',
      'b.tile.openstreetmap.fr',
      'c.tile.openstreetmap.fr',
    ]
    session.defaultSession.webRequest.onBeforeSendHeaders((details, cb) => {
      try {
        const u = new URL(details.url)
        if (OSM_HOSTS.includes(u.hostname)) {
          details.requestHeaders['User-Agent'] =
            'LocWarp-Mac/0.3 (+https://github.com/yhz601016/locwarp-mac)'
          details.requestHeaders['Referer'] = 'https://github.com/yhz601016/locwarp-mac'
        }
      } catch {}
      cb({ requestHeaders: details.requestHeaders })
    })
  } catch (e) { console.error('[electron] UA hook failed:', e) }

  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    title: 'LocWarp',
    backgroundColor: '#0f1117',
    show: false,
    // Native-looking title bar on macOS; the page draws its own header.
    titleBarStyle: IS_MAC ? 'hiddenInset' : 'default',
    trafficLightPosition: IS_MAC ? { x: 12, y: 12 } : undefined,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
      autoplayPolicy: 'no-user-gesture-required',
    },
  })
  mainWindow.once('ready-to-show', () => { mainWindow.show() })
  mainWindow.on('closed', () => { mainWindow = null })

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http://') || url.startsWith('https://')) {
      shell.openExternal(url)
    }
    return { action: 'deny' }
  })

  const isDev = process.argv.includes('--dev') || !app.isPackaged
  if (isDev) {
    mainWindow.loadURL('http://localhost:5173')
  } else {
    startBackend()
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'))
  }
}

// Single instance: a second launch just focuses the existing window instead
// of spawning a second backend that would fight over port 8777.
const gotLock = app.requestSingleInstanceLock()
if (!gotLock) {
  app.quit()
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore()
      mainWindow.focus()
    } else {
      createWindow()
    }
  })

  app.whenReady().then(createWindow)
  app.on('window-all-closed', () => {
    // macOS convention: keep the app (and the backend, so the iPhone keeps
    // its simulated location) alive until the user quits with ⌘Q.
    if (!IS_MAC) {
      stopBackend()
      app.quit()
    }
  })
  app.on('before-quit', stopBackend)
  app.on('will-quit', stopBackend)
  app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow() })
}

module.exports = { waitForBackend }
