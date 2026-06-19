# FCC Custom - Free Claude Code with NIM Fallback

A customized version of [Free Claude Code](https://github.com/Alishahryar1/free-claude-code) with enhanced NVIDIA NIM rate-limit fallback and admin UI improvements.

## Credits

**Original project:** [Alishahryar1/free-claude-code](https://github.com/Alishahryar1/free-claude-code)

This project is based on the excellent work by [Alishahryar1](https://github.com/Alishahryar1). All original code is licensed under MIT License.

## What's New (Custom Features)

### 1. NIM 429 Rate-Limit Fallback

Automatically switches to fallback API keys when primary key hits rate limit (429).

- **3 API keys** supported (Primary → Fallback → 2nd Fallback)
- **Immediate swap** on 429 (no retry delay)
- **Proactive rotation** after configurable number of requests (default: 20)

### 2. NIM Model Tester (Admin UI)

Test response times for NVIDIA NIM models directly from admin panel.

- Search/filter 121+ models
- Select models → see them in right panel
- Test all selected → get response times
- Save/load/delete model lists

### 3. Configurable Settings

- `NIM_PROACTIVE_ROTATE_AFTER` - Rotate key after N requests

## Installation

### Option 1: Install Script (Recommended)

```powershell
# Install base FCC first
irm "https://github.com/Alishahryar1/free-claude-code/blob/main/scripts/install.ps1?raw=1" | iex

# Then apply custom patches
git clone https://github.com/YOUR_USERNAME/fcc-custom.git
cd fcc-custom
.\install.ps1
```

### Option 2: Manual

```powershell
# Install base FCC
uv tool install free-claude-code

# Copy custom sitecustomize.py
Copy-Item .\sitecustomize.py "C:\Users\$env:USERNAME\AppData\Roaming\uv\python\cpython-3.14-windows-x86_64-none\Lib\sitecustomize.py"

# Copy admin UI files
Copy-Item .\admin_static\* "C:\Users\$env:USERNAME\AppData\Roaming\uv\tools\free-claude-code\Lib\site-packages\api\admin_static\" -Recurse
```

## Configuration

Edit `~/.fcc/.env`:

```dotenv
# NVIDIA NIM keys
NVIDIA_NIM_API_KEY=nvapi-your-primary-key
NVIDIA_NIM_FALLBACK_API_KEY=nvapi-your-fallback-key
NVIDIA_NIM_2ND_FALLBACK_API_KEY=nvapi-your-2nd-fallback-key

# Optional: Rotate key after N requests (0 = disabled)
NIM_PROACTIVE_ROTATE_AFTER=20
```

Get free API key at: https://build.nvidia.com/settings/api-keys

## Usage

```powershell
# Start proxy
fcc-server

# In another terminal, run Claude Code
fcc-claude
```

Admin UI: http://127.0.0.1:8082/admin

## Technical Details

### How Fallback Works

```
Request → FCC Server
           ↓
    execute_with_retry()
           ↓ (if 429)
    sitecustomize.py patches:
    1. Swap to next key immediately
    2. Reset rate limiter (5s instead of 60s)
    3. Retry with new key
```

### Files Modified

| File | Purpose |
|------|---------|
| `sitecustomize.py` | Runtime monkey-patch (loads at Python startup) |
| `api/admin_static/admin.js` | NIM Tester UI logic |
| `api/admin_static/admin.css` | NIM Tester styles |
| `api/admin_static/index.html` | NIM Tester layout |
| `api/admin_routes.py` | NIM API endpoints |

### Important Notes

- `sitecustomize.py` is in Python lib, NOT in FCC directory
- Changes take effect immediately (no restart needed for patches)
- Admin UI changes need browser refresh (Ctrl+Shift+R)

## License

MIT License - Same as original project.

See [LICENSE](LICENSE) for details.

## Acknowledgments

- [Alishahryar1](https://github.com/Alishahryar1) - Original Free Claude Code project
- [NVIDIA](https://nvidia.com) - Free NIM API for developers
