# FCC Custom - Session Memory

## Project Overview
Custom patches for Free Claude Code (Alishahryar1/free-claude-code) adding NIM multi-key fallback and admin UI improvements.

## Repository
- **Local:** `C:\Users\Admin\Desktop\githubprojects\fcc-custom`
- **GitHub:** https://github.com/tungbach12/fcc-custom
- **Upstream:** https://github.com/Alishahryar1/free-claude-code

## Current Versions
| Component | Version |
|-----------|---------|
| FCC installed | v1.2.41 |
| Patch version | v1.0.0 |
| Patched FCC version | v1.2.41 |

## Architecture

### How Patches Work
```
fcc-custom repo (source)
    ↓ install.ps1
sitecustomize.py → Python lib (runtime monkey-patch)
admin_static/ → FCC admin UI
```

**sitecustomize.py** loads at Python startup, patches:
1. `providers/rate_limit.py` → `execute_with_retry` (immediate 429 swap)
2. `providers/nvidia_nim/client.py` → `_create_stream` (proactive rotation + logging)
3. `providers/error_mapping.py` → `map_error` (5s block instead of 60s)

### Why sitecustomize.py?
- FCC exe embeds Python — source in site-packages is NOT the running code
- `.pth` files not processed by FCC's embedded Python
- `sitecustomize.py` loads at Python startup regardless

## Key Files

### Live Files (running)
| File | Path |
|------|------|
| sitecustomize.py | `C:\Users\Admin\AppData\Roaming\uv\python\cpython-3.14-windows-x86_64-none\Lib\sitecustomize.py` |
| .env | `C:\Users\Admin\.fcc\.env` |
| nim_patch.log | `C:\Users\Admin\.fcc\nim_patch.log` |
| server.log | `C:\Users\Admin\.fcc\logs\server.log` |

### Repo Files (source)
| File | Purpose |
|------|---------|
| sitecustomize.py | Runtime monkey-patch |
| patch_version.json | Tracks patched APIs and signatures |
| install.ps1 | Install script with version check |
| check_updates.ps1 | Check upstream + custom updates |
| admin_static/ | NIM Tester UI (admin.js, admin.css, index.html) |
| .env.example | Placeholder keys only |
| docs/NIM_FALLBACK_IMPLEMENTATION.md | Technical docs |

## Features Implemented

### 1. NIM Multi-Key Fallback
- 3 API keys supported (Primary → Fallback → 2nd Fallback)
- Immediate swap on 429 (no retry delay)
- Proactive rotation after configurable request count (default: 20)
- Keys read directly from `.env` file (not os.environ)

### 2. NIM Model Tester (Admin UI)
- Search/filter 121+ NIM models
- Select models → see in right panel
- Test all selected → get response times + status
- Save/load/delete model lists (persisted to nim_saved_lists.json)
- Error messages truncated to 40 chars, hover for full

### 3. Auto-Detection
- Version tracking (PATCH_VERSION, PATCHED_FCC_VERSION)
- API compatibility checks on startup
- check_updates.ps1 for checking upstream + custom updates
- install.ps1 tests patch application after install

## Config (.env)
```bash
NVIDIA_NIM_API_KEY=nvapi-xxx
NVIDIA_NIM_FALLBACK_API_KEY=nvapi-yyy
NVIDIA_NIM_2ND_FALLBACK_API_KEY=nvapi-zzz
NIM_PROACTIVE_ROTATE_AFTER=20
```

## Console Log Format
```
[NIM] key=1/3 req#1 model=moonshotai/kimi-k2.6
```

## Important Notes

### NIM Rate Limits
- 40 rq/min per account
- Per-model rate limits (different models have separate limits)
- 429 causes account-wide temporary ban (5s–5min+)
- Same IP possible detection; multiple keys from different accounts help

### FCC Server
- Port: 8082
- Auth: `x-api-key: freecc` (from ANTHROPIC_AUTH_TOKEN)
- API: Anthropic Messages (`/v1/messages`), NOT OpenAI chat completions
- NIM API auth: `Authorization: Bearer <key>` (NOT x-api-key)

### NIM Tester
- Tests bypass FCC pipeline (direct API calls)
- Fallback NOT triggered in NIM Tester (only in chat pipeline)
- To test all keys, need to test each separately

## Sync Strategy
- Repo contains only patches, not full codebase
- When upstream updates:
  1. Check if patched APIs changed signatures
  2. Update sitecustomize.py if needed
  3. Users re-run install.ps1
- No need to fork entire codebase

## PR #865 Analysis
- **Title:** Fix Claude auto-mode classifier thinking policy
- **Status:** OPEN (not merged into v1.2.41)
- **Conflict with patches:** NONE
- **Files changed:** api/detection.py, api/request_pipeline.py, providers/base.py, providers/wafer/client.py
- **Our patches:** providers/rate_limit.py, providers/nvidia_nim/client.py, providers/error_mapping.py
- **Safe to apply:** Yes

## Known Issues
- NIM Tester tests don't trigger fallback (by design — direct API calls)
- Deepseek models often rate-limited on all keys
- Per-model rate limits mean rotating keys may not help all models

## Update Commands
```powershell
# Check for updates
.\check_updates.ps1

# Reinstall patches
.\install.ps1

# Check FCC version
Get-ChildItem "$env:APPDATA\uv\tools\free-claude-code\Lib\site-packages\free_claude_code-*.dist-info"

# View patch log
Get-Content "$env:USERPROFILE\.fcc\nim_patch.log" -Tail 20
```

## License
MIT License
- Original: Copyright (c) 2026 Ali Khokhar (Alishahryar1)
- Modified: Copyright (c) 2026 tungbach12

## Credits
- Original project: https://github.com/Alishahryar1/free-claude-code
- NVIDIA NIM: https://build.nvidia.com
