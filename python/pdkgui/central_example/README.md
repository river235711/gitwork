# central 範例(golden command file + fab deck pointer)

這是 `config.DEFAULT_COM_DIR`(中央 golden 目錄)的**範例**。實際使用時把它放到你的
central 路徑,或用環境變數 `PDKGUI_DEFAULT_DIR` 指過來。

## 結構

```
<CENTRAL>/
└── <DESIGN>/                     例:t22_1p7m_4x1z1u/
    ├── <MODULE>.com              golden 命令檔範本(LoadDefault 讀這個)
    └── <MODULE>.inc              最新 fab deck 路徑(一行)
```

本範例含一個 design `t22_1p7m_4x1z1u`,模組 DRC / ANT / WB / BUMP / DMDV / DPDO / LVS / XRC
各一組 `.com` + `.inc`。

## pdkgui 怎麼用它

- 開 tab 時(且無 session)→ 讀 `<DESIGN>/<MODULE>.com` 進文字框。
- 開 tab **與** 按 Run → 把文字框裡的 `include <...>` 行換成 `<DESIGN>/<MODULE>.inc` 的值。
- `.inc` 是 fab deck 路徑的唯一真實來源:deck 更新時**只改 `.inc` 一行**,所有人下次開/跑就吃到。

## 怎麼套用

擇一:

1. 複製到你的 central 目錄(即 `config.DEFAULT_COM_DIR`):
   ```bash
   cp -r central_example/* <你的 CENTRAL>/
   ```
2. 或直接把 central 指到這個範例(測試用):
   ```bash
   export PDKGUI_DEFAULT_DIR=/home/willhuang/work/gitwork/python/pdkgui/central_example
   ```

## 新增其他 design

複製 `t22_1p7m_4x1z1u/` 成新 design 名(對應 PROCESS 選項,如 `t22_1p8m_5x1z1u/`),
再改各 `.com` / `.inc` 內容即可:

```bash
cp -r central_example/t22_1p7m_4x1z1u central_example/t22_1p8m_5x1z1u
# 編輯 central_example/t22_1p8m_5x1z1u/*.inc 填該 design 的 deck 路徑
```

## deck 更新(日常維運)

```bash
echo /datacenter/.../CLN22ULP_7M_4X1Z1U_<新版>.encrypt \
    > <CENTRAL>/t22_1p7m_4x1z1u/DRC.inc
```

> `.com` 裡的 `CELL_NAME` / `./CELL_NAME.gds` 是佔位;實際會由使用者填欄位或載入版圖後帶入。
> `.inc` 內的 deck 路徑為範例格式,請換成你 PDK 的實際路徑。
