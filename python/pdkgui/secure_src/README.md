# 程式碼加密 (pdkgui secure code)

把不想被使用者直接讀到的 Python 原始碼「加密」成 `.pdkc`,由 pdkgui 在
執行期解密後執行,磁碟上不留明文。

## 元件

| 檔案 | 作用 |
|------|------|
| `pdkcrypt.py` | 加密核心(純 stdlib):PBKDF2 派生金鑰 + HMAC-CTR 加密 + encrypt-then-MAC |
| `pdk_pack.py` | 打包工具:`.py` → 加密的 `.pdkc` |
| `pdk_secure.py` | 執行期載入器:解密 → compile → exec |
| `secure_src/` | 受保護原始碼的保管處(明文,**不部署**) |
| `data/secure/*.pdkc` | 加密後的可部署檔 |
| `pages/secure.py` | SECURE tab:執行加密的 `secure_page.pdkc` |

## 使用流程

1. 在 `secure_src/` 寫 / 改原始碼(例:`secure_page.py`,需提供 `build(page)`)。
2. 設定金鑰並打包:
   ```bash
   export PDKGUI_KEY='your-secret-passphrase'
   python3 pdk_pack.py secure_src/secure_page.py data/secure/secure_page.pdkc
   ```
3. 執行 pdkgui,同一把金鑰要在執行環境設定:
   ```bash
   export PDKGUI_KEY='your-secret-passphrase'
   ./pdkgui        # 切到 SECURE tab 即由加密檔建立畫面
   ```
   也可單獨執行一支加密檔:`python3 pdk_secure.py data/secure/secure_page.pdkc`

> 未設定 `PDKGUI_KEY` 時會使用 `pdkcrypt.DEFAULT_PASSPHRASE`(僅供測試,請務必改掉)。

## 安全性等級(務必了解)

這是 **client-side 保護**:解密金鑰最終要跟程式一起交到使用者手上,所以本質是
「靜態加密 + 混淆」——磁碟上是密文、明文原始碼只短暫存在記憶體。可擋一般使用者
直接 `cat`/讀檔,但**擋不住**有心人反組譯或 dump 記憶體。

若要更強的保護:
- **Cython**:把 `.py` 編成 `.so`(原生碼,難反編譯)。
- **PyArmor** 等商用工具。

部署時建議只發佈 `.pdkc`,不要把 `secure_src/` 的明文一起放到使用者可讀的路徑。
