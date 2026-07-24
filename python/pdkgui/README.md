# pdkgui

仿內部 EDA 流程管理工具的 Tkinter GUI(PROCESS / ENV / DRC / ANT / WB / BUMP /
DMDV / DPDO / LVS / XRC / JIVARO / SKIPPER / KLAYOUT / DOC / SYSTEM)。

## 檔案架構

```
pdkgui/
├── pdkgui              啟動包裝 (bash):module load 含 tkinter 的 python 再執行
├── pdkgui.py           bootstrap(明文,無邏輯):裝加密 import hook → pdkgui_app.main()
├── pdkgui_app.py       主視窗 + 左側選單 + 頁面路由
├── config.py           集中設定(每個 tab 讀哪個檔、路徑、常數)
├── widgets.py          共用元件(ScrolledText 雙滾輪、LogoPanel)
├── pages/              各 tab 頁面
│   ├── base.py  process.py  env.py  verify.py  skipper.py
│   ├── klayout.py  doc.py  system.py  __init__.py(頁面註冊表)
├── data/               各 tab 讀取的內容檔(system.txt / env.txt / verify/*.com / doc/*)
├── pdkcrypt.py         加密核心(純 stdlib:PBKDF2 + HMAC-CTR + encrypt-then-MAC)
├── pdk_secure.py       執行期載入器 + 加密模組 import hook
├── pdk_pack.py         單檔加密工具(.py → .pdkc)
└── pdk_build.py        產生整包加密部署版 dist/
```

## 執行(開發)

在原始碼目錄直接執行(沒有 .pdkc 時 import hook 自動略過,照常載入明文 .py):

```bash
./pdkgui                 # 或  python3 pdkgui.py
```

launcher 會透過 Environment Modules `module load python/3.6.3` 取得含 tkinter 的
python(可用 `PDKGUI_MODULE` / `PDKGUI_PYTHON` 覆蓋),並在背景啟動。需要 X display
(`ssh -X`)。

## 加密部署

```bash
python3 pdk_build.py dist        # 產生 dist/;金鑰會釘進 dist/pdkcrypt.py
dist/pdkgui                      # 直接執行,免設任何環境變數
```

- `dist/` 內只有 bootstrap 與解密器是明文,其餘(`config`/`widgets`/`pdkgui_app`/
  `pages/*`)都是 `.pdkc`,使用者 trace/讀檔看不到邏輯原始碼。
- 金鑰**釘進 `dist/pdkcrypt.py`**,執行時忽略環境變數 —— 搬到哪、環境有沒有殘留
  `PDKGUI_KEY` 都能跑,不必 unset。想用自訂金鑰:`PDKGUI_KEY=xxx python3 pdk_build.py dist`。
- `dist/` 是可重建的產物,**不進 repo**;要部署時重跑 `pdk_build.py` 即可。

### 安全性等級

client-side 保護 = **靜態加密 + 混淆**:解密金鑰終究隨程式一起發佈,磁碟上是密文、
明文只短暫存在記憶體。可擋一般使用者 `cat`/trace,但擋不住反組譯或 dump 記憶體。
要更強請改用 **Cython**(編成 `.so`)或 **PyArmor** 等工具。

## 預設 command file(中央 golden 目錄)

verify 類頁面(DRC/ANT/WB/BUMP/DMDV/DPDO/LVS/XRC)的「預設 command file」放在中央目錄,
依 design 分子目錄(用 `config.DEFAULT_COM_DIR` 設定,或環境變數 `PDKGUI_DEFAULT_DIR` 覆蓋):

```
<DEFAULT_COM_DIR>/<DESIGN>/<MODULE>.com     golden 命令檔範本(LoadDefault 讀這個)
<DEFAULT_COM_DIR>/<DESIGN>/<MODULE>.inc     最新 fab deck 路徑(一行,選用)
```

- LoadDefault 按鈕讀 `.com`;central 讀不到才退回內建範本 `data/verify/<MODULE>.com`。
- `.inc`(選用)放**最新 fab PDK deck 路徑**(一行)。pdkgui **開 tab 與按 Run** 時,會把
  command 裡的 `include <...>` 行換成 `.inc` 的值 —— deck 一更新只要改這個一行檔,所有人
  下次開/跑就自動吃到新路徑。`.inc` 不存在則不動 command 原本的 include(向後相容)。
  例:`echo /datacenter/.../CLN22ULP_..._<新版>.encrypt > <DEFAULT_COM_DIR>/<DESIGN>/DRC.inc`

## 使用者狀態 `~/.pdkgui/`

各人「上次」的欄位與 command 文字存這裡(可用 `PDKGUI_USER_DIR` 覆蓋根目錄):

```
~/.pdkgui/session/<DESIGN>/<MODULE>.json    每個 tab 上次的工作狀態(欄位 + command)
```

開 tab 讀取順序:**session(上次)→ central default → 內建範本**。
