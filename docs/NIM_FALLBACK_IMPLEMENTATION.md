# NVIDIA NIM Fallback API Key - Implementation Guide

## Overview

Hệ thống tự động chuyển sang API key khác khi primary key bị rate limit (429).

**Keys:** Primary → Fallback → 2nd Fallback

---

## Files Modified

| File | Purpose | Effective |
|------|---------|-----------|
| `sitecustomize.py` | Runtime monkey-patch | Yes (always) |
| `api/admin_config.py` | Admin UI field | Yes (after restart) |
| `providers/nvidia_nim/client.py` | Source code | No (exe embedded) |

---

## How to Add More Keys

### Step 1: Add env var to `.env`

```bash
NVIDIA_NIM_API_KEY=nvapi-xxx
NVIDIA_NIM_FALLBACK_API_KEY=nvapi-yyy
NVIDIA_NIM_2ND_FALLBACK_API_KEY=nvapi-zzz
NVIDIA_NIM_3RD_FALLBACK_API_KEY=nvapi-aaa  # new key
```

### Step 2: Add field to admin UI

File: `api/admin_config.py`

```python
ConfigFieldSpec(
    "NVIDIA_NIM_3RD_FALLBACK_API_KEY",
    "NVIDIA NIM 3rd Fallback API Key",
    "providers",
    "secret",
    secret=True,
    description="Optional 3rd fallback key for NIM 429 rate-limit retries.",
),
```

### Step 3: Update sitecustomize.py

```python
KEYS = [
    "NVIDIA_NIM_API_KEY",
    "NVIDIA_NIM_FALLBACK_API_KEY",
    "NVIDIA_NIM_2ND_FALLBACK_API_KEY",
    "NVIDIA_NIM_3RD_FALLBACK_API_KEY",  # add here
]
```

### Step 4: Update client.py

```python
_NIM_KEY_ENVS = [
    "NVIDIA_NIM_API_KEY",
    "NVIDIA_NIM_FALLBACK_API_KEY",
    "NVIDIA_NIM_2ND_FALLBACK_API_KEY",
    "NVIDIA_NIM_3RD_FALLBACK_API_KEY",  # add here
]
```

### Step 5: Restart FCC

```powershell
Get-Process -Name fcc-server -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Process -FilePath "$env:USERPROFILE\.local\bin\fcc-server.exe" -WindowStyle Hidden
```

---

## Errors We Faced & How to Fix

### Error 1: `_fallback_api_key` always None

**Lỗi:** Fallback key không bao giờ được dùng.

**Nguyên nhân:** `__init__` đọc `os.environ.get(_FALLBACK_ENV)` khi server start, nhưng `.env` load SAU provider init → env var chưa có.

**Fix:** Đọc key tại runtime, không cache trong `__init__`:

```python
# WRONG (cache at init)
self._fallback_api_key = os.environ.get(_FALLBACK_ENV)

# RIGHT (read at runtime)
def _get_retry_request_body(self, error, body):
    fallback = os.environ.get(FALLBACK_ENV)  # read when needed
```

---

### Error 2: `.pth` file không load

**Lỗi:** Tạo `nim_fallback.pth` trong `site-packages` nhưng không hiệu lực.

**Nguyên nhân:** FCC exe dùng embedded Python, `.pth` files không được process.

**Fix:** Dùng `sitecustomize.py` thay vì `.pth`:

```python
# Location: C:\Users\Admin\AppData\Roaming\uv\python\cpython-3.14-windows-x86_64-none\Lib\sitecustomize.py
# This file is ALWAYS loaded at Python startup
```

---

### Error 3: Override `_create_stream` không áp dụng

**Lỗi:** Thêm `_create_stream` override trong `client.py` nhưng code chạy vẫn dùng base class.

**Nguyên nhân:** FCC exe embedded Python - source trong `site-packages` KHÔNG được dùng. Code thật nằm trong ZIP của exe.

**Fix:** Monkey-patch class method qua `sitecustomize.py`:

```python
def _patch_nim():
    from providers.nvidia_nim.client import NvidiaNimProvider
    orig = NvidiaNimProvider._get_retry_request_body
    
    def patched(self, error, body, _orig=orig):
        # your logic here
        return _orig(self, error, body)
    
    NvidiaNimProvider._get_retry_request_body = patched
```

---

### Error 4: `NameError: name '_FALLBACK_ENV' is not defined`

**Lỗi:** Server crash khi request.

**Nguyên nhân:** Xóa biến `_FALLBACK_ENV` trong `client.py` nhưng `__init__` vẫn dùng.

**Fix:** Xóa line引用 trong `__init__`:

```python
# WRONG
def __init__(self, ...):
    self._fallback_api_key = os.environ.get(_FALLBACK_ENV)  # _FALLBACK_ENV deleted!

# RIGHT
def __init__(self, ...):
    pass  # remove the line entirely
```

---

### Error 5: 404 on `/v1/chat/completions`

**Lỗi:** Test endpoint `/v1/chat/completions` trả 404.

**Nguyên nhân:** FCC dùng Anthropic Messages API, không phải OpenAI chat completions.

**Fix:** Dùng đúng endpoint:

```bash
# WRONG
POST /v1/chat/completions

# RIGHT
POST /v1/messages
```

---

### Error 6: Admin UI field shows "template" label

**Lỗi:** Label field mới hiển thị "NVIDIA NIM 2nd Fallback API Key template".

**Nguyên nhân:** Field chưa có value trong `.env`, source type = "template".

**Fix:** Không cần fix - đây là behavior đúng. Nhập value và click Apply sẽ change thành "managed_env".

---

### Error 7: Response returns error message as content

**Lỗi:** Response 200 OK nhưng content chứa error message thay vì AI response.

**Nguyên nhân:** `sitecustomize.py` không đọc được key từ `.env` (os.environ rỗng).

**Fix:** Đọc trực tiếp file `.env`:

```python
_ENV_FILE = os.path.join(os.environ.get("USERPROFILE", ""), ".fcc", ".env")

def _load_env_keys():
    keys = {}
    with open(_ENV_FILE) as f:
        for line in f:
            for name in KEYS:
                if line.startswith(name + "="):
                    keys[name] = line[len(name)+1:].strip()
    return keys
```

---

### Error 8: Sitecustomize blocks FCC startup

**Lỗi:** FCC start xong model discovery nhưng không listen port.

**Nguyên nhân:** Import loop hoặc blocking import trong `sitecustomize.py`.

**Fix:** Import trong thread, không block main thread:

```python
def _patch_nim():
    for _ in range(120):  # retry import
        try:
            from providers.nvidia_nim.client import NvidiaNimProvider
            break
        except Exception:
            time.sleep(1)

t = threading.Thread(target=_patch_nim, daemon=True)
t.start()  # non-blocking
```

---

## Debug Commands

### Check if patch applied

```powershell
& "C:\Users\Admin\AppData\Roaming\uv\python\cpython-3.14-windows-x86_64-none\python.exe" -c "
from providers.nvidia_nim.client import NvidiaNimProvider
print(NvidiaNimProvider._get_retry_request_body.__module__)
"
# Output: sitecustomize (OK) vs nvidia_nim.client (not patched)
```

### Check 429 and key swap in log

```powershell
Get-Content "$env:USERPROFILE\.fcc\logs\server.log" -Tail 20 | Select-String "429|rate limit|SWAPPED"
```

### Check admin UI fields

```powershell
# Navigate to http://127.0.0.1:8082/admin
# Providers section shows all NIM key fields
```

### Test request

```powershell
$body = '{"model":"nvidia_nim/stepfun-ai/step-3.7-flash","messages":[{"role":"user","content":"Say hi"}],"max_tokens":20}'
Add-Type -AssemblyName System.Net.Http
$handler = [System.Net.Http.HttpClientHandler]::new()
$client = [System.Net.Http.HttpClient]::new($handler)
$client.DefaultRequestHeaders.Add("x-api-key", "freecc")
$content = [System.Net.Http.StringContent]::new($body, [System.Text.Encoding]::UTF8, "application/json")
$resp = $client.PostAsync("http://127.0.0.1:8082/v1/messages", $content).Result
"Status: $($resp.StatusCode)"
```

---

## Architecture

```
Request → FCC Server
           ↓
    NvidiaNimProvider._create_stream()
           ↓
    execute_with_retry(max_retries=2)  ← retry 2 times
           ↓ (if still 429)
    _get_retry_request_body()
           ↓
    Cycle keys: primary → fallback → 2nd fallback
           ↓
    self._client.api_key = new_key
    self._global_rate_limiter.set_blocked(0)  ← reset rate limit
           ↓
    Return body (retry with new key)
```

---

## Key Notes

1. **sitecustomize.py** = runtime patch (hiệu lực ngay)
2. **client.py** = source code (chỉ dùng khi install từ source, KHÔNG dùng với exe)
3. **os.environ** = rỗng vì FCC dùng `dotenv` (không set vào env)
4. **Không tự động quay lại key 1** - cần thêm logic nếu muốn
5. **Key rỗng** = skip, hệ thống vẫn hoạt động với ít key hơn

---

## NIM Model Tester - Admin UI

### Overview

Công cụ test response time của các model trên NVIDIA NIM, tích hợp trong admin UI (`/admin`).

### Files Modified

| File | Purpose |
|------|---------|
| `api/admin_static/index.html` | HTML layout cho NIM Tester |
| `api/admin_static/admin.js` | JS logic: search, select, test, save/load |
| `api/admin_static/admin.css` | CSS styles cho NIM Tester |
| `api/admin_routes.py` | API endpoints: `/admin/api/nim/*` |

### Features

1. **Search box** - Filter 121+ models real-time
2. **Select All / None** - Bulk select/deselect filtered models
3. **Selected models panel** - Hiển thị bên phải khi select, status "Ready"
4. **Test All Selected** - Test parallel, cập nhật OK/Error + response time (ms)
5. **Saved Lists** - Save/Load/Delete danh sách models (persisted to `nim_saved_lists.json`)
6. **Error truncation** - Lỗi dài bị rút gọn, hover để xem full

### How It Works

```
User selects models → Right panel shows "Ready"
         ↓
Click "Test All Selected"
         ↓
POST /admin/api/nim/test { model, max_tokens: 20 }
         ↓
Response: { ok: true, elapsed_ms: 775 }
         ↓
Right panel updates: OK (green) + 775ms
```

### API Endpoints

```bash
# List all available NIM models
GET /admin/api/nim/models

# Test single model
POST /admin/api/nim/test
Body: { "model": "deepseek-ai/deepseek-v4-flash", "max_tokens": 20 }

# Get saved lists
GET /admin/api/nim/saved

# Save a list
POST /admin/api/nim/saved
Body: { "name": "fast-models", "models": ["model1", "model2"] }

# Delete a list
DELETE /admin/api/nim/saved/{name}
```

### Bugs Fixed

#### Bug 1: `renderSections is not defined` error

**Lỗi:** Console error `renderSections is not defined` khi mở NIM Tester.

**Nguyên nhân:** `renderSections` crash khi `view.containerId` là `null` (NIM Tester không có containerId).

**Fix:** Thêm null check trong `renderSections`:

```javascript
const container = byId(view.containerId);
if (container) container.innerHTML = "";
```

#### Bug 2: Error messages too long in results

**Lỗi:** Lỗi 404/429 hiển thị full JSON response, phá vỡ layout.

**Fix:** truncate error messages:

```javascript
const err = result.error || "Error";
const shortErr = err.length > 40 ? err.substring(0, 37) + "..." : err;
statusEl.textContent = shortErr;
statusEl.title = err; // hover to see full
```

#### Bug 3: Test results cleared on re-test

**Lỗi:** Khi test lại, kết quả cũ bị xóa sạch thay vì cập nhật.

**Fix:** Dùng `row.id` để tìm và cập nhật in-place:

```javascript
const rowId = `nim-result-${model.replace(/[\/\.]/g, "-")}`;
const row = byId(rowId);
if (row) {
  statusEl.textContent = "Testing...";
}
```

#### Bug 4: Selected models not shown in right panel

**Lỗi:** Phải click Test mới thấy kết quả, không thấy danh sách đã select.

**Fix:** Thêm `renderSelectedModels()` gọi khi selection thay đổi:

```javascript
cb.addEventListener("change", () => {
  cb.checked ? nimState.selectedModels.add(model) : nimState.selectedModels.delete(model);
  updateNimSelectedCount();
  renderSelectedModels(); // ← thêm dòng này
});
```

### Key Notes

1. **NIM models endpoint** - Fetches live from `https://integrate.api.nvidia.com/v1/models`
2. **Test uses `max_tokens: 20`** - Chỉ test nhanh, không generate nhiều
3. **Parallel testing** - `Promise.all()` test nhiều models cùng lúc
4. **Saved lists** - Lưu vào `~/.fcc/nim_saved_lists.json`, không cần restart
5. **Org name styling** - Part trước `/` hiển thị màu accent (green)

### Location

```
FCC exe: C:\Users\Admin\.local\bin\free-claude-code.exe
Admin UI: http://127.0.0.1:8082/admin
Static files: C:\Users\Admin\AppData\Roaming\uv\tools\free-claude-code\Lib\site-packages\api\admin_static\
```
