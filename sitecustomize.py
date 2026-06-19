"""NIM multi-key fallback patch for Free Claude Code."""
import os
import random
import sys
import threading
import time
import inspect

_ENV_FILE = os.path.join(os.environ.get("USERPROFILE", ""), ".fcc", ".env")
_MAX_REQ = 35
_DBG = os.path.join(os.environ.get("USERPROFILE", ""), ".fcc", "nim_patch.log")

# Version tracking - update when patching new FCC versions
PATCH_VERSION = "1.0.0"
PATCHED_FCC_VERSION = "1.2.41"  # Version this patch was designed for

_NIM_KEY_ENVS = [
    "NVIDIA_NIM_API_KEY",
    "NVIDIA_NIM_FALLBACK_API_KEY",
    "NVIDIA_NIM_2ND_FALLBACK_API_KEY",
]


def _log(msg):
    with open(_DBG, "a") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")


def _get_fcc_version():
    """Get installed FCC version from package metadata."""
    try:
        import importlib.metadata
        return importlib.metadata.version("free-claude-code")
    except Exception:
        pass
    # Fallback: scan dist-info directories
    try:
        site_packages = [p for p in sys.path if "site-packages" in p][0]
        for d in os.listdir(site_packages):
            if d.startswith("free_claude_code-") and d.endswith(".dist-info"):
                return d.replace("free_claude_code-", "").replace(".dist-info", "")
    except Exception:
        pass
    return None


def _check_api_compat():
    """Check if patched APIs still have expected signatures."""
    issues = []
    try:
        from providers.rate_limit import GlobalRateLimiter
        sig = inspect.signature(GlobalRateLimiter.execute_with_retry)
        params = list(sig.parameters.keys())
        if "fn" not in params:
            issues.append("execute_with_retry missing 'fn' param")
        if "max_retries" not in params:
            issues.append("execute_with_retry missing 'max_retries' param")
    except Exception as e:
        issues.append(f"execute_with_retry check failed: {e}")

    try:
        from providers.nvidia_nim.client import NvidiaNimProvider
        if not hasattr(NvidiaNimProvider, "_create_stream"):
            issues.append("_create_stream method not found")
    except Exception as e:
        issues.append(f"_create_stream check failed: {e}")

    try:
        from providers import error_mapping as em
        if not callable(getattr(em, "map_error", None)):
            issues.append("map_error function not found")
    except Exception as e:
        issues.append(f"map_error check failed: {e}")

    return issues


def _version_check():
    """Check FCC version and API compatibility."""
    installed = _get_fcc_version()
    _log(f"FCC version: {installed} (patch designed for: {PATCHED_FCC_VERSION})")

    if installed and installed != PATCHED_FCC_VERSION:
        _log(f"WARNING: Version mismatch! Installed={installed}, Patched={PATCHED_FCC_VERSION}")
        _log("Patches may not work correctly. Re-run install.ps1 or update sitecustomize.py")

    issues = _check_api_compat()
    if issues:
        for issue in issues:
            _log(f"API COMPAT ISSUE: {issue}")
        _log("Some patches may not apply correctly")
    else:
        _log("API compatibility check passed")


def _load_env_file():
    values = {}
    if not os.path.exists(_ENV_FILE):
        return values
    with open(_ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, val = line.partition("=")
                values[key.strip()] = val.strip()
    return values


def _patch_nim():
    _log("patch_nim started")
    _version_check()
    for i in range(120):
        try:
            from providers.nvidia_nim.client import NvidiaNimProvider
            from providers.rate_limit import GlobalRateLimiter
            import openai
            _log(f"import OK after {i}s")
            break
        except Exception as e:
            _log(f"import attempt {i}: {e}")
            time.sleep(1)
    else:
        _log("FAILED: could not import after 120s")
        return

    env = _load_env_file()

    # Load keys
    key_pairs = []
    seen_vals = set()
    for name in _NIM_KEY_ENVS:
        val = env.get(name, "").strip()
        if val and val not in seen_vals:
            key_pairs.append((name, val))
            seen_vals.add(val)

    _log(f"keys loaded: {len(key_pairs)}")
    if len(key_pairs) < 2:
        _log("need >=2 keys, skipping")
        return

    # Load proactive rotate count from env (default 20)
    max_req_str = env.get("NIM_PROACTIVE_ROTATE_AFTER", "20").strip()
    try:
        max_req = int(max_req_str) if max_req_str else 20
    except ValueError:
        max_req = 20
    if max_req < 0:
        max_req = 0
    _log(f"proactive rotate after: {max_req} requests")

    # Inject keys into os.environ
    for env_name, val in key_pairs:
        os.environ[env_name] = val
    _log("injected keys into os.environ")

    key_list = [v for _, v in key_pairs]
    state = {"current_key_index": 0, "request_count": 0}

    # Patch execute_with_retry for IMMEDIATE key swap on 429
    orig_execute = GlobalRateLimiter.execute_with_retry

    async def patched_execute(self, fn, *args, max_retries=4,
                              base_delay=1.0, max_delay=60.0, jitter=2.0,
                              _orig=orig_execute, _keys=key_list, _state=state,
                              **kwargs):
        from providers.rate_limit import retryable_upstream_status
        last_exc = None
        total_attempts = 1 + max_retries

        for attempt in range(total_attempts):
            await self.wait_if_blocked()
            try:
                return await fn(*args, **kwargs)
            except Exception as e:
                status = retryable_upstream_status(e)
                if status is None:
                    raise

                is_429 = status == 429 or isinstance(e, openai.RateLimitError)
                last_exc = e

                if not is_429:
                    if attempt >= max_retries:
                        break
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    delay += random.uniform(0, jitter)
                    import asyncio
                    await asyncio.sleep(delay)
                    continue

                # 429: swap key IMMEDIATELY, no delay
                old = _state["current_key_index"]
                _state["current_key_index"] = (old + 1) % len(_keys)
                new_key = _keys[_state["current_key_index"]]

                provider = _state.get("_provider_ref")
                if provider is not None:
                    provider._client.api_key = new_key
                if _state["current_key_index"] < len(_NIM_KEY_ENVS):
                    os.environ[_NIM_KEY_ENVS[_state["current_key_index"]]] = new_key

                self.set_blocked(0)
                _state["request_count"] = 0
                _log(f"429 ROTATE key {old + 1} -> {_state['current_key_index'] + 1} (attempt {attempt + 1})")
                continue

        if last_exc is not None:
            raise last_exc

    GlobalRateLimiter.execute_with_retry = patched_execute
    _log("execute_with_retry patched")

    # Patch _create_stream for proactive rotation
    orig_create = NvidiaNimProvider._create_stream

    async def patched_create(self, body, _orig=orig_create, _keys=key_list, _state=state, _max_req=max_req):
        state["_provider_ref"] = self
        _state["request_count"] += 1
        key_num = _state["current_key_index"] + 1
        model = body.get("model", "?")
        print(f"[NIM] key={key_num}/{len(_keys)} req#{_state['request_count']} model={model}", flush=True)

        if _max_req > 0 and _state["request_count"] >= _max_req:
            old = _state["current_key_index"]
            _state["current_key_index"] = (old + 1) % len(_keys)
            new_key = _keys[_state["current_key_index"]]
            self._client.api_key = new_key
            if _state["current_key_index"] < len(_NIM_KEY_ENVS):
                os.environ[_NIM_KEY_ENVS[_state["current_key_index"]]] = new_key
            self._global_rate_limiter.set_blocked(0)
            _state["request_count"] = 0
            _log(f"PROACTIVE rotate key {old + 1} -> {_state['current_key_index'] + 1} (after {_max_req} reqs)")

        return await _orig(self, body)

    NvidiaNimProvider._create_stream = patched_create
    _log("_create_stream patched")

    # Patch map_error to use shorter block for 429 (5s instead of 60s)
    try:
        from providers import error_mapping as em
        orig_map_error = em.map_error

        def patched_map_error(e, rate_limiter=None, _orig=orig_map_error):
            result = _orig(e, rate_limiter=rate_limiter)
            if isinstance(result, Exception) and "rate_limit" in getattr(result, '__class__.__name__', '').lower():
                if rate_limiter is not None:
                    rate_limiter.set_blocked(5.0)
            return result

        em.map_error = patched_map_error
        _log("map_error patched (set_blocked 5s for rate_limit)")
    except Exception as e:
        _log(f"map_error patch failed: {e}")

    _log("ALL DONE")


t = threading.Thread(target=_patch_nim, daemon=True)
t.start()
