import sys
import os
import functools
from typing import Optional, Callable, Any
from rich.console import Console
from rich.tree import Tree
from rich.panel import Panel

_cwd = os.getcwd()
_backtrace_file = os.path.abspath(__file__)
_console = Console()


def _get_relative_path(filepath: str) -> str:
    try:
        return os.path.relpath(filepath, _cwd)
    except ValueError:
        return filepath


def _get_function_name(frame) -> str:
    code = frame.f_code
    func_name = code.co_name
    
    if func_name == '<module>':
        local_vars = frame.f_locals
        for name, value in local_vars.items():
            if callable(value) and hasattr(value, '__code__') and value.__code__ == code:
                return name
    
    return func_name


def _should_trace(filepath: str) -> bool:
    abspath = os.path.abspath(filepath)
    
    if abspath == _backtrace_file:
        return False
    
    if 'site-packages' in abspath:
        return False
    if 'dist-packages' in abspath:
        return False
    if sys.prefix in abspath and _cwd not in abspath:
        return False
    
    return True


class _TraceContext:
    def __init__(self, target_code, log_file: Optional[str] = None, return_trace: bool = False, use_rich: bool = True):
        self.target_code = target_code
        self.log_file = log_file
        self.return_trace = return_trace
        self.use_rich = use_rich
        self.events = []
        self.exception_info = None
        self.started = False
        self.root_frame = None
        
    def trace_func(self, frame, event, arg):
        code = frame.f_code
        filepath = code.co_filename
        
        if not _should_trace(filepath):
            return self.trace_func
        
        if not self.started and code == self.target_code:
            self.started = True
            self.root_frame = frame
        
        if not self.started:
            return self.trace_func
        
        lineno = frame.f_lineno
        func_name = _get_function_name(frame)
        rel_path = _get_relative_path(filepath)
        
        if event == 'call':
            if frame.f_back and frame != self.root_frame:
                caller_lineno = frame.f_back.f_lineno
                caller_path = _get_relative_path(frame.f_back.f_code.co_filename)
                self.events.append(('call', caller_path, caller_lineno, func_name, None))
            else:
                self.events.append(('call', rel_path, lineno, func_name, None))
            
        elif event == 'return':
            self.events.append(('return', rel_path, lineno, func_name, None))
                
        elif event == 'exception':
            exc_type, exc_value, exc_tb = arg
            self.exception_info = (exc_type, exc_value, rel_path, lineno, func_name)
            self.events.append(('exception', rel_path, lineno, func_name, (exc_type, exc_value)))
        
        return self.trace_func
    
    def _build_tree(self, is_failure: bool = False) -> Tree:
        if not self.events:
            return Tree("No events captured")
        
        first_event = self.events[0]
        root_label = f"[cyan]↳[/cyan] {first_event[1]}:{first_event[2]} [yellow]({first_event[3]})[/yellow]"
        tree = Tree(root_label)
        
        stack = [tree]
        
        for i, (event_type, filepath, lineno, func_name, exc_info) in enumerate(self.events[1:], 1):
            if event_type == 'call':
                label = f"[cyan]↳[/cyan] {filepath}:{lineno} [yellow]({func_name})[/yellow]"
                node = stack[-1].add(label)
                stack.append(node)
            elif event_type == 'return':
                label = f"[green]↰[/green] {filepath} [yellow]({func_name})[/yellow]"
                if len(stack) > 1:
                    stack[-1].add(label)
                    stack.pop()
            elif event_type == 'exception':
                exc_type, exc_value = exc_info
                if is_failure:
                    label = f"[red]✗[/red] {filepath}:{lineno} [yellow]({func_name})[/yellow] [red]<-- EXCEPTION: {exc_type.__name__}: {exc_value}[/red]"
                else:
                    label = f"[yellow]⚠[/yellow] {filepath}:{lineno} [yellow]({func_name})[/yellow] [dim]<-- handled exception: {exc_type.__name__}: {exc_value}[/dim]"
                stack[-1].add(label)
        
        return tree
    
    def _format_plain(self, status: str, is_failure: bool = False) -> str:
        lines = []
        depth = 0
        
        for event_type, filepath, lineno, func_name, exc_info in self.events:
            indent = "    " * depth
            
            if event_type == 'call':
                lines.append(f"{indent}↳ {filepath}:{lineno} ({func_name})")
                depth += 1
            elif event_type == 'return':
                depth -= 1
                indent = "    " * depth
                lines.append(f"{indent}↰ {filepath} ({func_name})")
            elif event_type == 'exception':
                exc_type, exc_value = exc_info
                if is_failure:
                    lines.append(f"{indent}✗ {filepath}:{lineno} ({func_name}) <-- EXCEPTION HERE: {exc_type.__name__}: {exc_value}")
                else:
                    lines.append(f"{indent}⚠ {filepath}:{lineno} ({func_name}) (handled exception: {exc_type.__name__})")
        
        if is_failure and self.exception_info:
            exc_type, exc_value, rel_path, lineno, func_name = self.exception_info
            header = f"EXCEPTION: {exc_type.__name__}: {exc_value} at {rel_path}:{lineno}"
        else:
            if self.events:
                first = self.events[0]
                header = f"EXECUTION TRACE (no exception) at {first[1]}:{first[2]}"
            else:
                header = "EXECUTION TRACE (no exception)"
        
        output = [
            header,
            "=== BACKTRACE ===",
            *lines,
            "=================",
            f"STATUS: {status}"
        ]
        return "\n".join(output)
    
    def format_trace(self, status: str, is_failure: bool = False):
        if not self.use_rich:
            return self._format_plain(status, is_failure)
        
        if is_failure and self.exception_info:
            exc_type, exc_value, rel_path, lineno, func_name = self.exception_info
            title = f"[red bold]EXCEPTION: {exc_type.__name__}[/red bold]"
            subtitle = f"{exc_value} at {rel_path}:{lineno}"
            status_color = "red"
        else:
            title = "[green bold]EXECUTION TRACE[/green bold]"
            subtitle = "no exception" if not self.exception_info else "exception handled"
            status_color = "green"
        
        tree = self._build_tree(is_failure)
        
        return Panel(
            tree,
            title=title,
            subtitle=subtitle,
            border_style=status_color,
            padding=(1, 2)
        )
    
    def output_trace(self, trace_output):
        if self.return_trace:
            return trace_output if isinstance(trace_output, str) else str(trace_output)
        elif self.log_file:
            content = trace_output if isinstance(trace_output, str) else str(trace_output)
            with open(self.log_file, 'a') as f:
                f.write(content + "\n")
        else:
            if self.use_rich and not isinstance(trace_output, str):
                _console.print(trace_output)
            else:
                print(trace_output)


def trace_calls(
    log_file: Optional[str] = None,
    return_trace: bool = False,
    trace_on_success: bool = True,
    use_rich: bool = True
):
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            ctx = _TraceContext(func.__code__, log_file, return_trace, use_rich)
            
            old_trace = sys.gettrace()
            sys.settrace(ctx.trace_func)
            
            try:
                result = func(*args, **kwargs)
                
                if trace_on_success:
                    trace_output = ctx.format_trace("PASS", is_failure=False)
                    ctx.output_trace(trace_output)
                
                return result
                
            finally:
                sys.settrace(old_trace)
                
                exc_info = sys.exc_info()
                if exc_info[0] is not None:
                    trace_output = ctx.format_trace("FAIL", is_failure=True)
                    ctx.output_trace(trace_output)
        
        return wrapper
    
    if callable(log_file):
        func = log_file
        log_file = None
        return decorator(func)
    
    return decorator


def run_and_log_backtrace(
    func: Callable,
    *args,
    log_file: Optional[str] = None,
    return_trace: bool = False,
    trace_on_success: bool = True,
    use_rich: bool = True,
    **kwargs
) -> Any:
    decorated = trace_calls(
        log_file=log_file,
        return_trace=return_trace,
        trace_on_success=trace_on_success,
        use_rich=use_rich
    )(func)
    return decorated(*args, **kwargs)


def log_warning(
    warning: Warning,
    log_file: Optional[str] = None,
    return_trace: bool = False,
    use_rich: bool = True
) -> Optional[str]:
    warning_type = type(warning).__name__
    message = str(warning)
    
    frame = sys._getframe(1)
    filepath = frame.f_code.co_filename
    lineno = frame.f_lineno
    rel_path = _get_relative_path(filepath)
    
    if use_rich:
        panel = Panel(
            f"[yellow]↳[/yellow] {rel_path}:{lineno} (warning_site)",
            title=f"[yellow bold]WARNING: {warning_type}[/yellow bold]",
            subtitle=message,
            border_style="yellow",
            padding=(1, 2)
        )
        
        if return_trace:
            return str(panel)
        elif log_file:
            with open(log_file, 'a') as f:
                f.write(str(panel) + "\n")
        else:
            _console.print(panel)
    else:
        header = f"WARNING: {warning_type}: {message} at {rel_path}:{lineno}"
        output = [
            header,
            "=== BACKTRACE ===",
            f"↳ {rel_path}:{lineno} (warning_site)",
            "=================",
            "STATUS: WARNING"
        ]
        trace_str = "\n".join(output)
        
        if return_trace:
            return trace_str
        elif log_file:
            with open(log_file, 'a') as f:
                f.write(trace_str + "\n")
        else:
            print(trace_str)