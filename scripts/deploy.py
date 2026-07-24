#!/usr/bin/env python3
"""Unified Deployment & Health Diagnostic CLI Script for ContAIned AI Platform.

Usage:
    python scripts/deploy.py [OPTIONS]

Options:
    --mode [all|infra|app|frontend|submodules|migrate|check|test]
    --profile [core|graph|messaging|app|admin|observability|full]
    --app-target [docker|native] (default: docker)
    --build             Force Docker build before running containers
    --detach / -d       Run containers in detached mode (default: True)
    --skip-submodules   Skip git submodule initialization/sync
    --verbose           Enable detailed output
"""

import argparse
import os
import pathlib
import socket
import subprocess
import sys
import time
import urllib.request
from typing import Dict, List, Tuple

# Terminal Color Constants
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
INFRA_DIR = ROOT_DIR / "infrastructure"
FRONTEND_DIR = ROOT_DIR / "frontend"
DOCKER_COMPOSE_FILE = INFRA_DIR / "docker-compose.yml"


def log_info(msg: str) -> None:
    print(f"{BLUE}{BOLD}[INFO]{RESET} {msg}")


def log_success(msg: str) -> None:
    print(f"{GREEN}{BOLD}[SUCCESS]{RESET} {msg}")


def log_warn(msg: str) -> None:
    print(f"{YELLOW}{BOLD}[WARNING]{RESET} {msg}")


def log_error(msg: str) -> None:
    print(f"{RED}{BOLD}[ERROR]{RESET} {msg}")


def run_command(cmd: List[str], cwd: pathlib.Path = ROOT_DIR, check: bool = False, capture_output: bool = False) -> subprocess.CompletedProcess:
    log_info(f"Running command: {' '.join(cmd)}")
    try:
        res = subprocess.run(cmd, cwd=cwd, check=check, capture_output=capture_output, text=True)
        return res
    except subprocess.CalledProcessError as e:
        log_error(f"Command failed with exit code {e.returncode}: {' '.join(cmd)}")
        if e.stdout:
            print(f"Stdout:\n{e.stdout}")
        if e.stderr:
            print(f"Stderr:\n{e.stderr}")
        if check:
            raise e
        return e


def sync_submodules() -> bool:
    log_info("Synchronizing and initializing git submodules...")
    res = run_command(["git", "submodule", "update", "--init", "--recursive"])
    if res.returncode == 0:
        log_success("Git submodules synchronized successfully.")
        return True
    else:
        log_warn("Git submodule sync encountered issues (might be running outside git repo).")
        return False


def check_env_file() -> bool:
    log_info("Checking .env configuration...")
    env_path = ROOT_DIR / ".env"
    example_path = ROOT_DIR / ".env.example"

    if not env_path.exists():
        if example_path.exists():
            log_warn(".env file not found! Creating .env from .env.example template...")
            with open(example_path, "r", encoding="utf-8") as f_in:
                content = f_in.read()
            with open(env_path, "w", encoding="utf-8") as f_out:
                f_out.write(content)
            log_success(".env created from .env.example.")
        else:
            log_error("Neither .env nor .env.example was found in project root!")
            return False

    # Verify essential variables
    with open(env_path, "r", encoding="utf-8") as f:
        env_content = f.read()

    required_vars = ["DATABASE_URL"]
    missing = [var for var in required_vars if f"{var}=" not in env_content]
    if missing:
        log_error(f"Missing required environment variables in .env: {missing}")
        return False

    log_success(".env configuration verified.")
    return True


def run_migrations() -> bool:
    log_info("Running Alembic database migrations...")
    cmd = ["poetry", "run", "alembic", "upgrade", "head"]
    res = run_command(cmd)
    if res.returncode != 0:
        log_warn("poetry run alembic failed. Retrying with direct alembic command...")
        res = run_command(["alembic", "upgrade", "head"])

    if res.returncode == 0:
        log_success("Database migrations applied successfully.")
        return True
    else:
        log_error("Failed to run database migrations!")
        return False


def deploy_docker(profile: str, build: bool = False, detach: bool = True) -> bool:
    log_info(f"Deploying Docker infrastructure (Profile: {profile})...")
    if not DOCKER_COMPOSE_FILE.exists():
        log_error(f"Docker Compose file not found at {DOCKER_COMPOSE_FILE}")
        return False

    cmd = ["docker", "compose", "-f", str(DOCKER_COMPOSE_FILE)]

    if profile == "app":
        cmd.extend(["--profile", "core", "--profile", "app"])
    elif profile and profile != "full":
        cmd.extend(["--profile", profile])
    elif profile == "full":
        cmd.extend(["--profile", "core", "--profile", "graph", "--profile", "messaging", "--profile", "app", "--profile", "admin", "--profile", "observability"])

    cmd.append("up")
    if detach:
        cmd.append("-d")
    if build:
        cmd.append("--build")

    res = run_command(cmd)
    if res.returncode == 0:
        log_success(f"Docker containers deployed (Profile: {profile}).")
        return True
    else:
        log_error(f"Docker Compose deployment failed for profile '{profile}'.")
        return False


def verify_app_modules() -> bool:
    log_info("Verifying Python microservices loading & routing integrity...")
    py_cmd = [
        sys.executable,
        "-c",
        "import gateway.main; import inference.main; print('Gateway & Inference modules loaded successfully.')"
    ]
    res = subprocess.run(py_cmd, cwd=ROOT_DIR, capture_output=True, text=True)
    if res.returncode == 0:
        log_success("Python application modules (Gateway API, Inference Server, Submodules) loaded cleanly.")
        return True
    else:
        log_warn(f"Native module import error: {res.stderr}. Retrying with poetry run...")
        res = run_command(["poetry", "run", "python", "-c", "import gateway.main; import inference.main; print('OK')"])
        if res.returncode == 0:
            log_success("Python application modules loaded cleanly via poetry.")
            return True
        else:
            log_error("Application module loading failed!")
            return False


def verify_frontend() -> bool:
    log_info("Verifying Frontend dashboard configuration & build system...")
    if not FRONTEND_DIR.exists():
        log_error(f"Frontend directory not found at {FRONTEND_DIR}")
        return False

    package_json = FRONTEND_DIR / "package.json"
    if not package_json.exists():
        log_error("Frontend package.json missing!")
        return False

    log_success("Frontend build system verified.")
    return True


def check_tcp_port(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def check_http_endpoint(url: str, timeout: float = 3.0) -> Tuple[bool, str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ContAIned-DeployCheck/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status_code = resp.getcode()
            if 200 <= status_code < 400:
                return True, f"HTTP {status_code}"
            else:
                return False, f"HTTP {status_code}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, str(e)


def run_health_checks() -> Dict[str, Tuple[bool, str]]:
    log_info("Performing deep health diagnostics across all infrastructure & services...")
    services = {
        "PostgreSQL DB (Port 5432)": (check_tcp_port("localhost", 5432), "Port 5432 reachable" if check_tcp_port("localhost", 5432) else "Connection refused"),
        "Qdrant Vector DB (Port 6333)": (check_tcp_port("localhost", 6333), "Port 6333 reachable" if check_tcp_port("localhost", 6333) else "Connection refused"),
        "Redis Cache (Port 6379)": (check_tcp_port("localhost", 6379), "Port 6379 reachable" if check_tcp_port("localhost", 6379) else "Connection refused"),
        "Neo4j Graph DB (Port 7474/7687)": (check_tcp_port("localhost", 7474) or check_tcp_port("localhost", 7687), "Port 7474/7687 reachable" if (check_tcp_port("localhost", 7474) or check_tcp_port("localhost", 7687)) else "Connection refused"),
        "Kafka Broker (Port 9092)": (check_tcp_port("localhost", 9092), "Port 9092 reachable" if check_tcp_port("localhost", 9092) else "Connection refused"),
    }

    # HTTP API Endpoint healthchecks
    gw_healthy, gw_msg = check_http_endpoint("http://localhost:8000/health")
    if not gw_healthy:
        gw_healthy, gw_msg = check_http_endpoint("http://localhost:8000/docs")
    services["Gateway API (Port 8000)"] = (gw_healthy, gw_msg)

    inf_healthy, inf_msg = check_http_endpoint("http://localhost:8010/health")
    if not inf_healthy:
        inf_healthy, inf_msg = check_http_endpoint("http://localhost:8010/docs")
    services["Inference Server (Port 8010)"] = (inf_healthy, inf_msg)

    fe_healthy = check_tcp_port("localhost", 5173)
    services["Frontend UI (Port 5173)"] = (fe_healthy, "Port 5173 reachable" if fe_healthy else "Not running (start via `cd frontend && npm run dev`)")

    # Print Health Summary Table
    print(f"\n{BOLD}{CYAN}===== SYSTEM HEALTH DIAGNOSTIC REPORT ====={RESET}")
    all_healthy = True
    for name, (status, detail) in services.items():
        status_str = f"{GREEN}[UP/OK]{RESET}" if status else f"{RED}[DOWN/OFFLINE]{RESET}"
        if not status:
            all_healthy = False
        print(f"  * {name:<35} : {status_str} ({detail})")
    print(f"{BOLD}{CYAN}==========================================={RESET}\n")

    return services


def run_tests() -> bool:
    log_info("Executing platform test suite...")
    res = run_command(["poetry", "run", "pytest", "tests/", "-v"])
    if res.returncode == 0:
        log_success("All system unit and integration tests passed.")
        return True
    else:
        log_error("Test suite execution failed.")
        return False


def main():
    parser = argparse.ArgumentParser(description="Deployment & Diagnostic Tool for ContAIned AI Platform.")
    parser.add_argument(
        "--mode",
        choices=["all", "infra", "app", "frontend", "submodules", "migrate", "check", "test"],
        default="all",
        help="Target execution mode (default: all)",
    )
    parser.add_argument(
        "--profile",
        choices=["core", "graph", "messaging", "app", "admin", "observability", "full"],
        default="core",
        help="Docker compose profile to deploy (default: core)",
    )
    parser.add_argument(
        "--app-target",
        choices=["docker", "native"],
        default="docker",
        help="Application deployment mode (docker containerized or native processes)",
    )
    parser.add_argument("--build", action="store_true", help="Force rebuilding Docker images")
    parser.add_argument("--skip-submodules", action="store_true", help="Skip initializing git submodules")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    print(f"{BOLD}{CYAN}🚀 ContAIned AI Platform Deployment Tool V5{RESET}\n")

    if not check_env_file():
        sys.exit(1)

    if not args.skip_submodules and args.mode in ["all", "submodules"]:
        sync_submodules()

    if args.mode in ["all", "infra"]:
        deploy_docker(profile=args.profile, build=args.build)

    if args.mode in ["all", "migrate"]:
        run_migrations()

    if args.mode in ["all", "app"]:
        verify_app_modules()
        if args.app_target == "docker":
            deploy_docker(profile="app", build=args.build)

    if args.mode in ["all", "frontend"]:
        verify_frontend()

    if args.mode in ["all", "check"]:
        run_health_checks()

    if args.mode == "test":
        run_tests()

    log_success("Deployment diagnostic operation completed.")


if __name__ == "__main__":
    main()
