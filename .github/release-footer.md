## 安裝（macOS）

1. 下載對應 CPU 的 DMG：Apple Silicon（M1 / M2 / M3 / M4）選 `mac-arm64`，Intel Mac 選 `mac-x64`
2. 打開 DMG，把 **LocWarp** 拖到「應用程式」
3. 本程式未經 Apple 公證，第一次開啟請在終端機執行：
   ```bash
   xattr -cr /Applications/LocWarp.app
   ```
   然後再從「應用程式」開啟（或右鍵 → 打開）
4. iPhone 用 USB 接上 Mac，解鎖並按「信任」；iOS 17+ 請先開啟 設定 → 隱私權與安全性 → 開發者模式

不需要 sudo、不需要 Xcode、不需要 iTunes。詳細說明見 README。

---

LocWarp Mac 是 [keezxc1223/locwarp](https://github.com/keezxc1223/locwarp)（MIT）的 macOS 分支。
