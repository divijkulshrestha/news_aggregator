"""
Script to run Playwright end-to-end tests.
"""
import subprocess
import sys
from pathlib import Path

def main():
    """Run Playwright tests with pytest."""
    # Change to project directory
    project_dir = Path(__file__).parent
    
    # Run pytest with playwright
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/e2e",
        "-v",
        "--headed",
        "--browser", "chromium"
    ]
    
    print(f"Running: {' '.join(cmd)}")
    print("-" * 50)
    
    result = subprocess.run(cmd, cwd=project_dir)
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()
