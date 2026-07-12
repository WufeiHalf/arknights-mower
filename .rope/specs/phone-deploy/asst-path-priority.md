# MAA asst Module Path Priority on Linux/Phone

## Scope

When running mower on Linux (especially Termux proot on Android), the
`asst` Python binding must be loaded from `<maa_path>/Python/asst/`,
not from `site-packages`. This affects both `initialize_maa` (main
process) and `maa_check` (subprocess).

## Problem

`site-packages` may contain an old `asst` shim (e.g. from a prior
`pip install` of a MAA framework package). This shim can `Asst.load()`
successfully but `Asst.connect()` returns False, producing the error
"连接失败，请检查Maa日志！" with no useful asst.log.

Verified on phone: `/usr/local/lib/python3.12/dist-packages/asst/`
exists and shadows `/root/maa/Python/asst/` when `sys.path.append`
is used.

## Root Cause

The original upstream code uses `sys.path.append(asst_path)`, which
adds to the end. Python imports the first match, so if `site-packages`
has `asst`, it wins.

## Fix

Both `base_schedule.initialize_maa` and `maa_check.run_maa_connectivity_check`
must:

1. `sys.path.insert(0, asst_path)` (not `append`)
2. Purge stale `asst` modules from `sys.modules` if they don't
   originate from `asst_path`

```python
asst_path = str(maa_path / "Python")
if asst_path in sys.path:
    sys.path.remove(asst_path)
sys.path.insert(0, asst_path)
for module_name in list(sys.modules):
    if module_name == "asst" or module_name.startswith("asst."):
        module_file = getattr(sys.modules[module_name], "__file__", "") or ""
        if not module_file.startswith(asst_path):
            del sys.modules[module_name]
```

## Diagnostic

To verify which `asst` is loaded:

```python
import asst
print(asst.__file__)
# Wrong: /usr/local/lib/python3.12/dist-packages/asst/__init__.py
# Right: /root/maa/Python/asst/__init__.py
```

Or check the log line from `initialize_maa`:

```
Maa Python模块导入成功: /root/maa/Python/asst/asst.py
```
