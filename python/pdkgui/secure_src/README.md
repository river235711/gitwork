# 程式碼加密 (pdkgui code encryption)

把 pdkgui 的商業邏輯原始碼「加密」成 `.pdkc`,由 bootstrap 在執行期透過
import hook 解密載入,使用者在部署機器上 trace / 讀檔只會看到加密檔。

## 元件

| 檔案 | 作用 |
|------|------|
| `pdkcrypt.py` | 加密核心(純 stdlib):PBKDF2 派生金鑰 + HMAC-CTR 加密 + encrypt-then-MAC |
| `pdk_secure.py` | 執行期載入器 + import hook(`install_import_hook`);讓 `import config` 等從 `.pdkc` 載入 |
| `pdk_pack.py` | 單檔打包:`.py` → `.pdkc` |
| `pdk_build.py` | 產生整包加密部署版 `dist/` |
| `pdkgui.py` | bootstrap(明文,無邏輯):裝 hook → 執行 `pdkgui_app.main()` |

## 產生加密部署版

```bash
export PDKGUI_KEY='your-secret-passphrase'   # 打包與執行要同一把金鑰
python3 pdk_build.py dist
```

`dist/` 內只有 bootstrap 與解密器是明文,其餘(`config` / `widgets` /
`pdkgui_app` / `pages/*`)都是 `.pdkc`。部署到目標機器後:

```bash
export PDKGUI_HOME=/path/to/dist
export PDKGUI_KEY='your-secret-passphrase'
dist/pdkgui
```

> 開發時直接在原始碼目錄跑 `./pdkgui` 即可(沒有 `.pdkc`,hook 自動略過,
> 照常載入明文 `.py`);同一支 bootstrap 開發/部署共用。

## 安全性等級(務必了解)

這是 **client-side 保護 = 靜態加密 + 混淆**:解密金鑰終究要跟程式一起交到
使用者手上,所以磁碟上是密文、明文原始碼只短暫存在記憶體。可擋一般使用者
直接 `cat`/trace,但**擋不住**反組譯或 dump 記憶體。

更強的保護:
- **Cython**:把 `.py` 編成 `.so`(原生碼,難反編譯)。
- **PyArmor** 等商用工具。

部署時只發佈 `dist/`,不要把明文原始碼一起放到使用者可讀的路徑。
