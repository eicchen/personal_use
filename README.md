#Personal Use files
Just some random 

# Backtrace Tool

Quick call tracer for debugging. Shows what functions called what and where exceptions happened.

## Basic Usage
```python
from backtrace import trace_calls

# Decorator - shows trace every time
@trace_calls()
def my_function():
    helper()
    another_helper()
    return result

# Only show trace on errors
@trace_calls(trace_on_success=False)
def risky_stuff():
    # Only outputs if this crashes
    return do_something()

# Write to file instead of console
@trace_calls(log_file="debug.log")
def production_code():
    return process()

# Plain text (no colors/formatting)
@trace_calls(use_rich=False)
def simple_output():
    return calc()
```

## What You'll See

**Success:**
- Green box with tree showing function calls
- `↳` = entering function (shows line number where it was called)
- `↰` = exiting function

**Handled Exception:**
- Green box, says "exception handled"
- `⚠` = exception happened but was caught

**Unhandled Exception:**
- Red box showing the error
- `✗` = where the exception occurred
- Still raises the exception normally

## Notes

- Only traces your code (filters out pandas, numpy, stdlib, etc.)
- Shows where functions are *called from*, not where they're defined
- Zero performance impact when not using the decorator
