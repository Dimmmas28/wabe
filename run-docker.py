#!/usr/bin/env python3
"""
WABE Docker Runner
Simple script to build and run WABE in Docker with proper configuration.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def check_docker():
    """Check if Docker is installed and running."""
    try:
        subprocess.run(
            ["docker", "--version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Error: Docker is not installed or not running")
        print("   Install Docker: https://docs.docker.com/get-docker/")
        sys.exit(1)


def check_api_key():
    """Check if GOOGLE_API_KEY is available."""
    # Check environment variable first
    if os.getenv("GOOGLE_API_KEY"):
        return True

    # Check .env file
    env_file = Path(".env")
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                if line.startswith("GOOGLE_API_KEY=") and "=" in line:
                    _, value = line.split("=", 1)
                    if value.strip() and not value.strip().startswith("your_"):
                        return True

    return False


def build_image(tag: str, force: bool = False):
    """Build the Docker image."""
    # Check if image exists
    if not force:
        try:
            result = subprocess.run(
                ["docker", "images", "-q", tag],
                check=True,
                stdout=subprocess.PIPE,
                text=True,
            )
            if result.stdout.strip():
                print(f"✓ Image '{tag}' already exists (use --build to rebuild)")
                return
        except subprocess.CalledProcessError:
            pass

    print(f"🔨 Building Docker image '{tag}'...")
    print("   This may take 5-10 minutes on first build (downloading browsers)")
    try:
        subprocess.run(["docker", "build", "-t", tag, "."], check=True)
        print(f"✓ Image '{tag}' built successfully")
    except subprocess.CalledProcessError:
        print("❌ Failed to build Docker image")
        sys.exit(1)


def run_container(tag: str, show_logs: bool = False, env_file: str = ".env"):
    """Run the Docker container."""
    # Prepare volume mounts
    cwd = Path.cwd()
    output_dir = cwd / ".output"
    logs_dir = cwd / ".logs"

    # Ensure directories exist
    output_dir.mkdir(exist_ok=True)
    logs_dir.mkdir(exist_ok=True)

    # Build docker run command
    cmd = [
        "docker",
        "run",
        "--rm",  # Remove container after exit
    ]

    # Handle environment variables
    if Path(env_file).exists():
        cmd.extend(["--env-file", env_file])
    elif os.getenv("GOOGLE_API_KEY"):
        cmd.extend(["-e", f"GOOGLE_API_KEY={os.getenv('GOOGLE_API_KEY')}"])
    else:
        print("❌ Error: GOOGLE_API_KEY not found")
        print("   Set it in .env file or as environment variable:")
        print("   export GOOGLE_API_KEY=your_key")
        sys.exit(1)

    # Add volume mounts
    cmd.extend(
        [
            "-v",
            f"{output_dir}:/app/.output",
            "-v",
            f"{logs_dir}:/app/.logs",
        ]
    )

    # Add image and command
    cmd.append(tag)

    if show_logs:
        cmd.extend(
            [
                "uv",
                "run",
                "agentbeats-run",
                "scenarios/web_browser/scenario.toml",
                "--show-logs",
            ]
        )

    print(f"🚀 Running WABE evaluation...")
    if show_logs:
        print("   Live logs enabled")
    print(f"   Output: {output_dir}")
    print(f"   Logs: {logs_dir}")
    print()

    try:
        subprocess.run(cmd, check=True)
        print()
        print("✓ Evaluation completed successfully!")
        print(f"   Results: {output_dir}/browser_eval_*/")
    except subprocess.CalledProcessError as e:
        print()
        print(f"❌ Evaluation failed (exit code {e.returncode})")
        sys.exit(e.returncode)
    except KeyboardInterrupt:
        print()
        print("⚠️  Interrupted by user")
        sys.exit(130)


def main():
    parser = argparse.ArgumentParser(
        description="Build and run WABE in Docker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Build and run with .env file
  python run-docker.py

  # Force rebuild and run with live logs
  python run-docker.py --build --show-logs

  # Just build the image
  python run-docker.py --build-only

  # Run with custom env file
  python run-docker.py --env-file .env.production
        """,
    )

    parser.add_argument(
        "--build",
        action="store_true",
        help="Force rebuild the Docker image before running",
    )
    parser.add_argument(
        "--build-only",
        action="store_true",
        help="Only build the image, don't run",
    )
    parser.add_argument(
        "--show-logs",
        action="store_true",
        help="Show live logs during evaluation",
    )
    parser.add_argument(
        "--tag",
        default="wabe:latest",
        help="Docker image tag (default: wabe:latest)",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to environment file (default: .env)",
    )

    args = parser.parse_args()

    # Check prerequisites
    check_docker()

    # Build image
    if args.build or args.build_only:
        build_image(args.tag, force=True)
    else:
        build_image(args.tag, force=False)

    # Run container (unless build-only)
    if not args.build_only:
        if not check_api_key():
            print("❌ Error: GOOGLE_API_KEY not found")
            print("   Create .env file:")
            print("   echo 'GOOGLE_API_KEY=your_key_here' > .env")
            print()
            print("   Or set environment variable:")
            print("   export GOOGLE_API_KEY=your_key_here")
            sys.exit(1)

        run_container(args.tag, args.show_logs, args.env_file)


if __name__ == "__main__":
    main()
