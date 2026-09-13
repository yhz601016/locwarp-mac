# LocWarp Mac

**macOS 版 iOS 虛擬定位模擬器** — 用 Mac 控制 iPhone 的 GPS 位置，適合《Pikmin Bloom 皮克敏》這類需要「走路」的定位遊戲。支援直接跳點、導航步行、多點巡迴、繞點花農模式、隨機漫步、搖桿操作，USB 或 WiFi Tunnel 連線。

本專案是 [keezxc1223/locwarp](https://github.com/keezxc1223/locwarp)（MIT）的 macOS 分支，原版只支援 Windows。核心功能與 UI 完整保留，並針對 Mac 做了以下調整：

| 項目 | Windows 原版 | LocWarp Mac |
| --- | --- | --- |
| 權限 | 必須以系統管理員執行（wintun 建 TUN 介面） | **免 sudo**：改用 pymobiledevice3 的 userspace tunnel |
| USB 驅動 | 需安裝 iTunes / Apple Devices | macOS 內建 usbmuxd，**免安裝** |
| Developer Disk Image (DDI) | 需先用 Xcode / 3uTools 掛一次 | **自動下載並掛載**，不用 Xcode |
| 安裝檔 | NSIS `.exe` | `.dmg`（Apple Silicon + Intel） |
| iOS 新版支援 | 手動更新 | **GitHub Actions 每週自動追蹤 pymobiledevice3**，通過測試後自動發新版 |

> **免責聲明**：使用虛擬定位違反多數遊戲的服務條款，可能導致帳號受限。本專案僅供學習與測試，使用者需自行承擔風險。本專案不保證於所有 macOS / iOS 版本組合下皆能運作。

---

## 系統需求

- **macOS 13 Ventura 以上**（Apple Silicon M1–M4 或 Intel 皆可）
- **iPhone / iPad：iOS 17 以上為主要支援**（iOS 26.x 亦可）；iOS 16.x 走舊版 LegacyLocationService 路徑；iOS 15 以下不支援
- iPhone 需開啟 **開發者模式**（設定 → 隱私權與安全性 → 開發者模式）
- 首次掛載 DDI 需要網路（約 20 MB，之後會快取）
- **不需要** Xcode、iTunes、Homebrew、sudo

---

## 安裝（一般使用者）

1. 到 [Releases](https://github.com/yhz601016/locwarp-mac/releases) 下載對應 CPU 的 DMG：
   - Apple Silicon（M1 / M2 / M3 / M4）→ `LocWarp-x.y.z-mac-arm64.dmg`
   - Intel Mac → `LocWarp-x.y.z-mac-x64.dmg`
   - 不確定？點左上角  → 關於這台 Mac，看「晶片」或「處理器」
2. 打開 DMG，把 **LocWarp** 拖進「應用程式」
3. 本程式沒有 Apple 公證（需付費開發者帳號），**第一次開啟前**請在「終端機」執行一次：

   ```bash
   xattr -cr /Applications/LocWarp.app
   ```

   然後從「應用程式」打開 LocWarp（或右鍵 → 打開）。若系統仍攔截，到 系統設定 → 隱私權與安全性 最下方按「仍要打開」。
4. iPhone 用 USB 線接上 Mac，解鎖手機並在「信任這部電腦？」按 **信任**
5. LocWarp 會自動偵測裝置、自動掛載 DDI（第一次約 30 秒到 2 分鐘，畫面會顯示進度）、自動連線
6. 地圖上點一個位置 → **跳點**，iPhone 的定位就會改變

第一次有手機透過 WiFi 連進「手機控制」網頁時，macOS 會跳出「是否允許 LocWarp 接受連入連線」，按 **允許**。

---

## 皮克敏（Pikmin Bloom）使用建議

- **走路請用「導航」或「多點巡迴」，不要一直跳點**。皮克敏是靠步數 + 定位移動來種花、長花的，用 3–5 km/h 的步行速度最自然（速度預設「走路」即為 3.6 km/h 上下）。
- 跳遠距離時 LocWarp 會依距離顯示建議冷卻時間（1 km 內免冷卻、5 km 30 秒、25 km 5 分鐘… 最長 2 小時），跨國跳點請乖乖等冷卻。
- **花農模式**（繞一個點畫圈）適合在花圃附近持續種花；**隨機漫步**適合在住家附近自然走動。
- 「還原真實定位」按鈕會把 iPhone 的 GPS 交回系統；結束前記得按，或直接拔 USB（LocWarp 會自動清除模擬定位）。
- 皮克敏的步數來自 iPhone 的動作感測器，虛擬定位**不會**產生步數；要步數請搭配實際走動或其他方法。

---

## 免權限 vs 多裝置模式

| 模式 | 如何啟用 | 同時連線數 | 說明 |
| --- | --- | --- | --- |
| **userspace（預設）** | 直接開 LocWarp | 1 支 iPhone | pymobiledevice3 11.x 的純使用者空間 TCP/IP 堆疊，不需 root |
| **kernel** | 終端機 `sudo python3 start.py`（原始碼模式） | 最多 3 支 | 建立 macOS `utun` 介面，需 root；行為與 Windows 原版相同 |

也可以用環境變數強制：`LOCWARP_TUNNEL_MODE=userspace` / `kernel` / `auto`（預設 auto：root 就用 kernel，否則 userspace）。

後端啟動後可到 `http://127.0.0.1:8777/api/system/platform` 查看目前模式。

---

## iOS 系統更新後的持續支援

iOS 每次大改版，能不能繼續模擬定位取決於底層函式庫 [pymobiledevice3](https://github.com/doronz88/pymobiledevice3) 是否跟上。LocWarp Mac 把這件事自動化：

1. **`.github/workflows/pmd3-watch.yml`** 每週一檢查 PyPI 是否有新版 pymobiledevice3
2. 有新版就更新 `backend/requirements.txt`，並執行 `scripts/smoke_test_backend.py`：確認我們依賴的 API（userspace tunnel 開關、DDI 自動掛載、DVT 定位服務…）都還存在、後端能正常 import
3. 通過 → 自動 bump 版本、打 tag、觸發 **`build-mac.yml`** 在 GitHub 的 macOS runner 上重新打包 arm64 + x64 DMG 並發佈 Release
4. 失敗 → 自動開 Issue 提醒需要人工調整
5. 已安裝的 LocWarp 在「設定」頁會顯示「有新版本」，點一下就到 Release 頁下載

想立刻跟上某個 iOS 版本，也可以手動到 Actions 頁按 **Run workflow**（勾選 force 可強制重新發版）。

> 若 iPhone 已升到 pymobiledevice3 尚未支援的 iOS 版本，LocWarp 會在連線時報錯（通常是 tunnel 或 DVT 建立失敗）。此時請耐心等 pymobiledevice3 更新；通常在 iOS 正式版釋出後數天到數週內會跟上。

---

## 從原始碼執行（開發者）

```bash
# 需要 Python 3.13+（WiFi Tunnel 需要原生 TLS-PSK）與 Node.js 18+
brew install python@3.13 node

git clone https://github.com/yhz601016/locwarp-mac.git
cd locwarp-mac
python3.13 -m pip install -r backend/requirements.txt
(cd frontend && npm install)

# 一鍵啟動（後端 :8777 + Vite 前端 :5173，自動開瀏覽器）
python3.13 start.py
# 或直接雙擊 LocWarp.command

# 多裝置（kernel tunnel）模式
sudo python3.13 start.py --kernel-tunnel
```

要在開發時測 Electron 視窗本身（IPC、原生選單），另開一個終端機：

```bash
cd frontend && npx electron . --dev
```

停止：按 Enter / Ctrl+C，或 `python3 stop.py`。

---

## 打包 DMG

```bash
python3.13 -m pip install pyinstaller
./build-mac.sh          # 產出 frontend/release/LocWarp-<版本>-mac-<arch>.dmg
```

流程：PyInstaller 把後端打成 `dist-py/locwarp-backend/` → Vite 打包前端 → electron-builder 產 DMG，並在 `afterPack` 階段做 ad-hoc 簽章（Apple Silicon 要求所有二進位至少有 ad-hoc 簽名）。arm64 與 x64 必須在對應 CPU 的 Mac 上各跑一次；GitHub Actions 的 `build-mac.yml` 已用 matrix 同時處理兩種架構。

---

## 專案結構

```
locwarp-mac/
├── backend/                    # FastAPI + pymobiledevice3（Python 3.13）
│   ├── core/
│   │   ├── platform_compat.py  # ★ Mac 移植核心：tunnel 模式、權限、DDI 自動掛載開關
│   │   ├── device_manager.py   # 裝置探索、USB / WiFi Tunnel 連線、DDI 自動掛載
│   │   ├── wifi_tunnel.py      # in-process RemotePairing tunnel
│   │   └── simulation_engine.py, navigator.py, flower.py, random_walk.py, joystick.py …
│   ├── api/                    # HTTP / WebSocket 端點
│   ├── services/               # 路徑規劃、地理編碼、插值、書籤
│   └── locwarp-backend.spec    # PyInstaller（跨平台）
├── frontend/                   # Electron + React + Leaflet / MapLibre
│   ├── electron/main.js        # ★ macOS 原生選單、backend 啟動、定位（CoreLocationCLI / IP）
│   ├── build/afterPack.js      # ★ ad-hoc codesign
│   ├── build/icon.icns         # ★ Mac 圖示
│   └── src/repo.ts             # ★ 更新檢查用的 GitHub repo
├── scripts/
│   ├── check_pmd3_update.py    # ★ 比對 PyPI 最新 pymobiledevice3
│   └── smoke_test_backend.py   # ★ 升級後的 API 相容性冒煙測試
├── .github/workflows/
│   ├── build-mac.yml           # ★ arm64 + x64 DMG 建置與 Release
│   └── pmd3-watch.yml          # ★ 每週追蹤 pymobiledevice3、自動發版
├── start.py / stop.py          # 跨平台開發啟動器
├── LocWarp.command             # ★ Mac 雙擊啟動
└── build-mac.sh                # ★ 一鍵打包
```

★ = 本分支新增或大幅修改。

---

## 疑難排解

| 狀況 | 處理方式 |
| --- | --- |
| 打開 LocWarp 顯示「已損毀」或「無法打開」 | 執行 `xattr -cr /Applications/LocWarp.app` 後再開 |
| 找不到 iPhone | 換一條 USB 線（要能傳資料的）、iPhone 解鎖並按「信任」、在「Finder」側邊欄確認有看到 iPhone |
| 「開發者模式」選項沒出現 | LocWarp 連上後狀態列會有「顯示開發者模式選項」按鈕；點完到 iPhone 設定 → 隱私權與安全性 最下方開啟並重開機 |
| DDI 自動掛載失敗 | 確認 Mac 有網路、iPhone 已解鎖；拔插 USB 重試。仍失敗可用 `python3 -m pymobiledevice3 mounter auto-mount` 手動掛載，或關閉再開啟一次開發者模式 |
| `No such service: com.apple.instruments.dtservicehub` | DDI 沒掛上，同上 |
| 想同時控制 2–3 支 iPhone | 免權限模式一次只能一支；用 `sudo python3 start.py --kernel-tunnel`（原始碼模式） |
| WiFi Tunnel 建不起來 | 先確認 USB 模式正常、iPhone 與 Mac 在同一 WiFi、關掉 VPN；iPhone 鎖屏會讓 tunnel 斷線，建議關閉自動鎖定 |
| 手機控制網頁連不上 | 確認手機和 Mac 同一 WiFi；macOS 防火牆對話框要按「允許」（系統設定 → 網路 → 防火牆 → 選項） |
| 升級 iOS 後連不上 | 看 [Releases](https://github.com/yhz601016/locwarp-mac/releases) 是否有新版；或到 Actions 手動跑 `pymobiledevice3 update watch` |
| 要看 log | 選單 Help → Open Log Folder，或 `~/.locwarp/logs/backend.log` |

---

## 授權與致謝

- 本專案採 [MIT License](LICENSE)，保留原作者 [keezxc1223](https://github.com/keezxc1223/locwarp) 的版權聲明
- 底層 iOS 通訊：[pymobiledevice3](https://github.com/doronz88/pymobiledevice3)（doronz88）
- 地圖與路徑：OpenStreetMap、OSRM、Valhalla、BRouter、Nominatim、Photon、Open-Meteo
