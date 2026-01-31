import argparse
import asyncio
import os
import shlex
import signal
import subprocess
import sys
import time
import tomllib
from datetime import datetime
from pathlib import Path

import httpx
from a2a.client import A2ACardResolver
from dotenv import load_dotenv

load_dotenv(override=True)


def get_log_dir() -> Path:
    """Get the log directory path and create it if it doesn't exist."""
    log_dir = Path(os.getenv("LOG_DIR", ".logs"))
    log_dir.mkdir(exist_ok=True)
    return log_dir


def create_log_file(log_dir: Path, timestamp: str, agent_name: str):
    """Create a log file for an agent and return the file handle."""
    log_path = log_dir / f"{timestamp}_{agent_name}.log"
    return open(log_path, "w", buffering=1)  # Line buffered


class TeeFile:
    """Write to multiple file-like objects simultaneously."""

    def __init__(self, *files):
        self.files = files

    def write(self, data):
        for f in self.files:
            if f is not None:
                f.write(data)
                f.flush()
        return len(data)

    def flush(self):
        for f in self.files:
            if f is not None:
                f.flush()

    def fileno(self):
        # Return the first file's fileno if available
        for f in self.files:
            if f is not None and hasattr(f, "fileno"):
                try:
                    return f.fileno()
                except Exception:
                    pass
        raise OSError("No valid file descriptor")


async def wait_for_agents(cfg: dict, timeout: int = 30) -> bool:
    """Wait for all agents to be healthy and responding."""
    endpoints = []

    # Collect all endpoints to check
    for p in cfg["participants"]:
        if p.get("cmd"):  # Only check if there's a command (agent to start)
            endpoints.append(f"http://{p['host']}:{p['port']}")

    if cfg["green_agent"].get("cmd"):  # Only check if there's a command (host to start)
        endpoints.append(
            f"http://{cfg['green_agent']['host']}:{cfg['green_agent']['port']}"
        )

    if not endpoints:
        return True  # No agents to wait for

    print(f"Waiting for {len(endpoints)} agent(s) to be ready...")
    start_time = time.time()

    async def check_endpoint(endpoint: str) -> bool:
        """Check if an endpoint is responding by fetching the agent card."""
        try:
            async with httpx.AsyncClient(timeout=2) as client:
                resolver = A2ACardResolver(httpx_client=client, base_url=endpoint)
                await resolver.get_agent_card()
                return True
        except Exception:
            # Any exception means the agent is not ready
            return False

    while time.time() - start_time < timeout:
        ready_count = 0
        for endpoint in endpoints:
            if await check_endpoint(endpoint):
                ready_count += 1

        if ready_count == len(endpoints):
            return True

        print(f"  {ready_count}/{len(endpoints)} agents ready, waiting...")
        await asyncio.sleep(1)

    print(
        f"Timeout: Only {ready_count}/{len(endpoints)} agents became ready after {timeout}s"
    )
    return False


def parse_toml(scenario_path: str) -> dict:
    path = Path(scenario_path)
    if not path.exists():
        print(f"Error: Scenario file not found: {path}")
        sys.exit(1)

    data = tomllib.loads(path.read_text())

    def host_port(ep: str):
        s = ep or ""
        s = s.replace("http://", "").replace("https://", "")
        s = s.split("/", 1)[0]
        host, port = s.split(":", 1)
        return host, int(port)

    green_ep = data.get("green_agent", {}).get("endpoint", "")
    g_host, g_port = host_port(green_ep)
    green_cmd = data.get("green_agent", {}).get("cmd", "")

    parts = []
    for p in data.get("participants", []):
        if isinstance(p, dict) and "endpoint" in p:
            h, pt = host_port(p["endpoint"])
            parts.append(
                {
                    "role": str(p.get("role", "")),
                    "host": h,
                    "port": pt,
                    "cmd": p.get("cmd", ""),
                }
            )

    cfg = data.get("config", {})
    return {
        "green_agent": {"host": g_host, "port": g_port, "cmd": green_cmd},
        "participants": parts,
        "config": cfg,
    }


def main():
    parser = argparse.ArgumentParser(description="Run agent scenario")
    parser.add_argument("scenario", help="Path to scenario TOML file")
    parser.add_argument(
        "--show-logs",
        action="store_true",
        help="Show agent stdout/stderr in terminal (logs are always written to .logs/)",
    )
    parser.add_argument(
        "--serve-only",
        action="store_true",
        help="Start agent servers only without running evaluation",
    )
    parser.add_argument(
        "--purple-model",
        type=str,
        default=None,
        help="Model for purple agent (default: gemini-2.5-flash)",
    )
    parser.add_argument(
        "--eval-model",
        type=str,
        default=None,
        help="Model for green agent evaluation (default: gemini-2.5-flash)",
    )
    args = parser.parse_args()

    cfg = parse_toml(args.scenario)

    # Create timestamped log files
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_dir = get_log_dir()

    # Show logs either in terminal or to DEVNULL, but always write to files
    terminal_sink = None if args.show_logs or args.serve_only else subprocess.DEVNULL
    parent_bin = str(Path(sys.executable).parent)
    base_env = os.environ.copy()
    base_env["PATH"] = parent_bin + os.pathsep + base_env.get("PATH", "")

    # Set model environment variables if specified via CLI
    if args.purple_model:
        base_env["PURPLE_AGENT_MODEL"] = args.purple_model
        print(f"Purple agent model: {args.purple_model}")
    if args.eval_model:
        base_env["EVAL_MODEL"] = args.eval_model
        print(f"Eval model: {args.eval_model}")

    procs = []
    log_files = []
    try:
        print(f"Logs will be written to: {log_dir.absolute()}/")

        # start participant agents
        for p in cfg["participants"]:
            cmd_args = shlex.split(p.get("cmd", ""))
            if cmd_args:
                role = p["role"]
                print(f"Starting {role} at {p['host']}:{p['port']}")

                # Create log file for this agent
                log_file = create_log_file(log_dir, timestamp, role)
                log_files.append(log_file)

                # Create output sink: write to log file, optionally also to terminal
                if args.show_logs or args.serve_only:
                    output_sink = TeeFile(log_file, sys.stdout)
                    error_sink = TeeFile(log_file, sys.stderr)
                else:
                    output_sink = log_file
                    error_sink = log_file

                procs.append(
                    subprocess.Popen(
                        cmd_args,
                        env=base_env,
                        stdout=output_sink,
                        stderr=error_sink,
                        text=True,
                        start_new_session=True,
                    )
                )

        # start host
        green_cmd_args = shlex.split(cfg["green_agent"].get("cmd", ""))
        if green_cmd_args:
            print(
                f"Starting green agent at {cfg['green_agent']['host']}:{cfg['green_agent']['port']}"
            )

            # Create log file for green agent
            log_file = create_log_file(log_dir, timestamp, "green")
            log_files.append(log_file)

            # Create output sink: write to log file, optionally also to terminal
            if args.show_logs or args.serve_only:
                output_sink = TeeFile(log_file, sys.stdout)
                error_sink = TeeFile(log_file, sys.stderr)
            else:
                output_sink = log_file
                error_sink = log_file

            procs.append(
                subprocess.Popen(
                    green_cmd_args,
                    env=base_env,
                    stdout=output_sink,
                    stderr=error_sink,
                    text=True,
                    start_new_session=True,
                )
            )

        # Wait for all agents to be ready
        if not asyncio.run(wait_for_agents(cfg)):
            print("Error: Not all agents became ready. Exiting.")
            return

        print("Agents started. Press Ctrl+C to stop.")
        if args.serve_only:
            while True:
                for proc in procs:
                    if proc.poll() is not None:
                        print(f"Agent exited with code {proc.returncode}")
                        break
                    time.sleep(0.5)
        else:
            # Create log file for client/app
            log_file = create_log_file(log_dir, timestamp, "app")
            log_files.append(log_file)

            # Create output sink for client
            if args.show_logs:
                output_sink = TeeFile(log_file, sys.stdout)
                error_sink = TeeFile(log_file, sys.stderr)
            else:
                output_sink = log_file
                error_sink = log_file

            client_proc = subprocess.Popen(
                [sys.executable, "-m", "agentbeats.client_cli", args.scenario],
                env=base_env,
                stdout=output_sink,
                stderr=error_sink,
                text=True,
                start_new_session=True,
            )
            procs.append(client_proc)
            client_proc.wait()

    except KeyboardInterrupt:
        pass

    finally:
        print("\nShutting down...")
        for p in procs:
            if p.poll() is None:
                try:
                    os.killpg(p.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        time.sleep(1)
        for p in procs:
            if p.poll() is None:
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

        # Close all log files
        for log_file in log_files:
            try:
                log_file.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
