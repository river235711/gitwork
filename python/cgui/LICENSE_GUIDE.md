# cgui 離線授權與 Nuitka 編譯部署指南

本專案已整合 **Ed25519 離線數位簽章授權**、**防系統時間回撥（Anti-Tamper）**、**到期前 30 天提示與 14 天寬限期**，並支援透過 **Nuitka** 編譯為原生 Linux ELF 執行檔。

---

## 1. 發證端：產生金鑰與簽發 `.lic`（僅限開發/發證機保留）

> **注意：`lic_issuer/` 與 `private_key.pem` 僅供開發與發證端使用，切勿交付給客戶。**

### 1.1 產生 Ed25519 金鑰並自動寫入公鑰至程式
```bash
python3 lic_issuer/cgui_lic_admin.py keygen \
    --out-dir lic_issuer/keys \
    --embed cgui_license.py
```
此指令會產生：
- `lic_issuer/keys/private_key.pem`（權限 `0600`，用於簽發授權檔）
- `lic_issuer/keys/public_key.pem`
- 並將 XOR 遮罩後的 32-byte 公鑰自動更新至 `cgui_license.py`

### 1.2 簽發客戶授權檔（`.lic`）
```bash
python3 lic_issuer/cgui_lic_admin.py issue \
    --key lic_issuer/keys/private_key.pem \
    --customer cadsemi \
    --domain sirius-wireless.com \
    --expire 2036-11-20 \
    --features gui_pro,batch_char \
    --out cadsemi.lic
```
可選參數 `--grace-days 14`（預設寬限期為 14 天）；若要簽發不限制網域的評估／測試版授權，可指定 `--domain "*"`。

### 1.3 驗證授權檔內容與簽章
```bash
python3 lic_issuer/cgui_lic_admin.py verify --lic cadsemi.lic
```

---

## 2. 客戶端設定與授權檢查行為

### 2.1 環境變數設定（貼合 EDA 使用習慣）
在客戶端 `.cshrc` 加入：
```csh
setenv CADSEMI_LICENSE_FILE /proj/cad/lic/cadsemi.lic
```
（或 bash `.bashrc`：`export CADSEMI_LICENSE_FILE=/proj/cad/lic/cadsemi.lic`；同時相容舊版 `CTMP_LICENSE_FILE`）

若未設定 `CADSEMI_LICENSE_FILE`，程式會依序自動往上搜尋 `cadsemi.lic`（同時相容舊版 `ctmp.lic`）：
1. `<版本目錄>/cadsemi.lic`（例如 `/apps/cadsemi/pvflow/26.11.001/cadsemi.lic`）
2. `<產品目錄>/cadsemi.lic`（例如 `/apps/cadsemi/pvflow/cadsemi.lic`）
3. `<公司目錄>/license/cadsemi.lic`（例如 `/apps/cadsemi/license/cadsemi.lic` — 推薦正式部署放這裡，升級新版免重複製）

年度續約時，只需將新的 `.lic` 檔覆蓋原路徑，**不需重新編譯或重裝軟體**。

### 2.2 檢查與提示機制
1. **簽章驗證**：啟動時及執行 Run / Skipper / Klayout 前，以內嵌公鑰驗證 Ed25519 簽章，防止竄改到期日或欄位。
2. **網域綁定驗證（試用版預設關閉：`ENFORCE_DOMAIN = False`）**：試用版僅檢查 Ed25519 簽章、到期日與防竄改時間戳，`.lic` 內的 `domain` 僅作客戶標籤記錄，不限制客戶端機器網域以免測試環境 mismatch 導致 fail；若日後正式版需鎖定客戶網域，將 `cgui_license.py` 的 `ENFORCE_DOMAIN` 改回 `True` 後重新編譯，即會檢查 `/etc/resolv.conf`（`domain`/`search`）、NIS `domainname` 與主機 FQDN 是否符合 `domain`（或其子網域，`*` 代表不限網域）。
3. **防偷調系統時間（Anti-Tamper）**：每次通過驗證時會以 HMAC-SHA256 + 加密方式更新本機高水位時間戳記（`~/.pvflow/.lic_state`、`~/.cache/.pvflow_lic_ts`，容許 5 分鐘跨主機/NTP 微幅誤差）；若偵測到系統時間明顯倒撥，立即鎖死拒絕執行。
4. **到期前 30 天預警**：
   - 終端機以預設文字顏色輸出：`[Notice] License will expire on YYYY-MM-DD. Please contact support@cadsemi.com for renewal.`
   - GUI 底部狀態列轉為黃色提醒。
5. **到期後 14 天寬限期（Grace Period）**：
   - 仍可正常執行（避免 Tape-out 期間突發停擺），但每次啟動會跳出提醒視窗，且底部狀態列轉為橘色倒數警告。
6. **超過寬限期**：
   - 正式鎖定並顯示錯誤訊息（CLI 退出碼 `3`；GUI 彈窗提示並結束）。
7. **查詢授權狀態**：
   ```bash
   pvflow -L
   ```

---

## 3. 使用 Nuitka 編譯為原生 Linux ELF 執行檔

### 3.1 本機（Ubuntu）編譯步驟
```bash
python3 -m venv .build_venv
.build_venv/bin/pip install nuitka patchelf ordered-set zstandard
.build_venv/bin/python cgui_build_nuitka.py --mode standalone --version 26.11.001 --out dist/26.11.001
```
編譯產物位於 `dist/<version>/`（標準 EDA 發布目錄結構）：
- `bin/pvflow`：啟動 wrapper 腳本（含 `bin/cgui -> pvflow` 相容連結）
- `libexec/pvflow.bin`：原生 Linux ELF 執行檔與隔離的相依 `.so` 函式庫（無 `.py` 原始碼與 `.pyc` 位元碼）
- `data/`：離線說明文件與範本
- `etc/modulefile.example`：Environment Modules 範本

### 3.2 一鍵編譯相容 RHEL 7 / CentOS 7（`glibc 2.17`）的通用發行版（推薦）
若在 Ubuntu 24.04 直接編譯，`pvflow.bin` 會綁定較新的 glibc 而在 RHEL 7 / CentOS 7 上無法執行。本機已透過 WSL2 建立獨立的 `CentOS7Build`（CentOS 7.9 / glibc 2.17）編譯環境，並提供一鍵打包腳本 `build_rhel7.ps1`：

```powershell
powershell -ExecutionPolicy Bypass -File \\wsl.localhost\Ubuntu\home\willhuang\work\gitwork\python\cgui\build_rhel7.ps1
```
此腳本會自動：
1. 排除 `lic_issuer/`、`private_key.pem`、`tests/` 與暫存檔，只將乾淨原始碼送入 `CentOS7Build`
2. 以 CentOS 7.9（glibc 2.17）+ GCC 10 + Python 3.12.7 執行 Nuitka 編譯並驗證所有 ELF 的最高 GLIBC 版本 `<= 2.17`
3. 自動產出通吃 **RHEL 7 / CentOS 7 / RHEL 8 / RHEL 9 / Ubuntu** 的：
   - `dist/<version>/`（標準 EDA 目錄結構，零 `.py`）
   - `dist/pvflow_<version>_linux_x64.tar.gz`（解壓到 `/apps/cadsemi/pvflow/` 即可直接執行）
