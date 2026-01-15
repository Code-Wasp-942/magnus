# sdks/python/src/magnus/cli/commands.py
import sys
import json
import typer
from typing import List, Optional, Any, Dict, Tuple
from pathlib import Path
from rich.console import Console
from rich.theme import Theme

from .. import (
    MagnusError,
    submit_blueprint,
    run_blueprint,
    call_service,
)

# === UI Setup ===

custom_theme = Theme({
    "magnus.prefix": "blue",
    "magnus.error": "red bold",
    "magnus.success": "green",
})
console = Console(theme=custom_theme)

def print_msg(msg: str, end: str = "\n"):
    console.print(f"[magnus.prefix][Magnus][/magnus.prefix] {msg}", end=end, highlight=False)

def print_error(msg: str):
    console.print(f"[magnus.prefix][Magnus][/magnus.prefix] [magnus.error]Error:[/magnus.error] {msg}", highlight=False)

# === Argument Parsing Logic ===

def parse_cli_args(args: List[str]) -> Dict[str, Any]:
    """
    [Smart Parser] 用于 Magnus CLI 自身的控制参数 (如 --timeout, --verbose)。
    采用积极类型推断策略 (Int/Float/Bool)，方便内部逻辑处理。
    """
    params = {}
    i = 0
    while i < len(args):
        key = args[i]
        if key.startswith("--"):
            key = key[2:]
            
            # Check for value
            if i + 1 < len(args) and not args[i + 1].startswith("--"):
                value = args[i + 1]
                i += 2
            else:
                value = True  # Flag defaults to True
                i += 1
            
            # Type Inference
            if isinstance(value, str):
                lower_val = value.lower()
                if lower_val == "true": value = True
                elif lower_val == "false": value = False
                elif value.isdigit(): value = int(value)
                else:
                    try:
                        value = float(value)
                    except ValueError:
                        pass
            params[key] = value
        else:
            i += 1
    return params

def parse_blueprint_args(args: List[str]) -> Dict[str, str]:
    """
    [Raw Parser] 用于传递给 Blueprints 的业务参数。
    原则：不猜测，不转换。所有值均保持为字符串，类型转换由后端/蓝图负责。
    Example:
      --count 2   -> {"count": "2"}
      --enable    -> {"enable": "true"}
    """
    params = {}
    i = 0
    while i < len(args):
        key = args[i]
        if key.startswith("--"):
            key = key[2:]
            
            if i + 1 < len(args) and not args[i + 1].startswith("--"):
                value = args[i + 1] # Keep as raw string
                i += 2
            else:
                value = "true"      # Flag defaults to string "true"
                i += 1
            params[key] = value
        else:
            i += 1
    return params

def partition_args(raw_args: List[str]) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """
    根据 '--' 防波堤切分参数。
    Left Slice  -> CLI Args (Typed)
    Right Slice -> Blueprint Args (String)
    Default     -> All args belong to Blueprint
    """
    if "--" in raw_args:
        idx = raw_args.index("--")
        cli_slice = raw_args[:idx]
        bp_slice = raw_args[idx + 1:]
    else:
        cli_slice = []
        bp_slice = raw_args

    return parse_cli_args(cli_slice), parse_blueprint_args(bp_slice)

# === Configuration ===

DEFAULT_CLI_CONFIG = {
    "timeout": 10.0,      # HTTP Network Timeout
    "preference": True,   # User Preference
    "verbose": False,     # Debug Mode
    "poll_interval": 2.0  # Polling Interval (Run only)
}

def apply_cli_defaults(parsed_cli_args: Dict[str, Any], command_type: str = "submit") -> Dict[str, Any]:
    config = DEFAULT_CLI_CONFIG.copy()
    
    # 特殊逻辑：Run 模式下若未指定 timeout，默认应为无限等待 (None)，而非 submit 的 10s
    if command_type == "run" and "timeout" not in parsed_cli_args:
        config["timeout"] = None
        
    config.update(parsed_cli_args)
    return config

# === CLI App Definition ===

app = typer.Typer(
    name="magnus",
    help="Magnus CLI - Focus on your Blueprint.",
    add_completion=False,
    no_args_is_help=True,
)

@app.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True}
)
def submit(
    ctx: typer.Context,
    blueprint_id: str = typer.Argument(..., help="ID of the blueprint"),
):
    """
    Submit a blueprint job (Fire & Forget).
    All unrecognized arguments are passed to the blueprint as strings.
    """
    try:
        cli_args, bp_args = partition_args(ctx.args)
        cli_config = apply_cli_defaults(cli_args, command_type="submit")
        
        if cli_config["verbose"]:
            console.rule("[dim]DEBUG: Argument Partition[/dim]")
            console.print(f"[dim]CLI Config (Typed): {cli_config}[/dim]")
            console.print(f"[dim]Blueprint Args (String): {bp_args}[/dim]")
            console.rule()

        print_msg(f"Submitting blueprint [bold cyan]{blueprint_id}[/bold cyan]...")
        
        job_id = submit_blueprint(
            blueprint_id=blueprint_id,
            use_preference=cli_config["preference"],
            timeout=cli_config["timeout"],
            args=bp_args
        )
        
        print_msg(f"Job submitted successfully. Job ID: [green]{job_id}[/green]")
        
    except MagnusError as e:
        print_error(str(e))
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        raise typer.Exit(code=1)


@app.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True}
)
def run(
    ctx: typer.Context,
    blueprint_id: str = typer.Argument(..., help="ID of the blueprint"),
):
    """
    Execute a blueprint and wait for completion.
    """
    try:
        cli_args, bp_args = partition_args(ctx.args)
        cli_config = apply_cli_defaults(cli_args, command_type="run")

        if cli_config["verbose"]:
            console.rule("[dim]DEBUG: Argument Partition[/dim]")
            console.print(f"[dim]CLI Config (Typed): {cli_config}[/dim]")
            console.print(f"[dim]Blueprint Args (String): {bp_args}[/dim]")
            console.rule()

        print_msg(f"Running blueprint [bold cyan]{blueprint_id}[/bold cyan]...")
        
        with console.status(f"[magnus.prefix][Magnus][/magnus.prefix] Waiting for job completion...", spinner="dots"):
            result = run_blueprint(
                blueprint_id=blueprint_id,
                use_preference=cli_config["preference"],
                timeout=cli_config["timeout"],
                poll_interval=cli_config["poll_interval"],
                args=bp_args
            )
        
        console.print("")
        print_msg("Job finished.")
        console.rule("[bold green]MAGNUS RESULT[/bold green]")
        
        try:
            if isinstance(result, str):
                json_obj = json.loads(result)
                console.print_json(data=json_obj)
            else:
                console.print(result)
        except Exception:
            console.print(result)
        console.rule()

    except MagnusError as e:
        print_error(str(e))
        raise typer.Exit(code=1)
    except KeyboardInterrupt:
        print_msg("Interrupted by user.")
        raise typer.Exit(code=130)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        raise typer.Exit(code=1)


@app.command()
def call(
    ctx: typer.Context,
    service_id: str = typer.Argument(..., help="ID of the service"),
    payload: Optional[str] = typer.Argument(None, help="Data source: '@file.json', '-', or JSON string"),
):
    """
    Call a managed service via RPC.
    Use '--' to separate CLI options (like --timeout) from payload arguments if necessary.
    """
    try:
        # call 命令的参数同样支持智能解析 (Smart Parsing)
        cli_args, _ = partition_args(ctx.args)
        
        # 默认 60s 超时
        if "timeout" not in cli_args:
            cli_args["timeout"] = 60.0
            
        cli_config = apply_cli_defaults(cli_args)
        
        # Payload Loading
        content = ""
        if payload:
            if payload == "-":
                if sys.stdin.isatty():
                    print_msg("Reading payload from stdin...")
                content = sys.stdin.read()
            elif payload.startswith("@"):
                filepath = Path(payload[1:])
                if not filepath.exists():
                    raise typer.BadParameter(f"Payload file not found: {filepath}")
                content = filepath.read_text(encoding="utf-8")
            else:
                content = payload
        
        data = json.loads(content) if content else {}
        
        if cli_config["verbose"]:
             console.print(f"[dim]CLI Config: {cli_config}[/dim]")

        print_msg(f"Calling service [bold cyan]{service_id}[/bold cyan]...")
        
        response = call_service(
            service_id=service_id,
            payload=data,
            timeout=cli_config["timeout"]
        )
        
        if isinstance(response, (dict, list)):
            console.print_json(data=response)
        else:
            console.print(response)

    except MagnusError as e:
        print_error(str(e))
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()