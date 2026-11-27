# cgui Vendor License Issuer (`lic_issuer`)

**WARNING: Keep this entire directory (`lic_issuer/`) and `private_key.pem` strictly internal on your build machine. Never distribute them to customers.**

## Quick Usage

1. **Generate Ed25519 keypair and embed the public key into `cgui_license.py`**:
   ```bash
   python3 lic_issuer/cgui_lic_admin.py keygen --out-dir lic_issuer/keys --embed cgui_license.py
   ```

2. **Issue a customer `.lic` file**:
   ```bash
   python3 lic_issuer/cgui_lic_admin.py issue \
       --key lic_issuer/keys/private_key.pem \
       --customer cadsemi \
       --domain cadsemi.com \
       --expire 2036-11-20 \
       --features gui_pro,batch_char \
       --out cadsemi.lic
   ```

3. **Verify a `.lic` file** (cross-checked with both `cryptography` and `cgui_license`'s pure-Python Ed25519 verifier):
   ```bash
   python3 lic_issuer/cgui_lic_admin.py verify --lic cadsemi.lic
   ```
