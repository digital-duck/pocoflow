"""Utility: safe Python code execution in subprocess."""

import os
import sys
import subprocess
import tempfile


def execute_python(code: str, timeout: int = 10) -> str:
    """Execute Python code in a subprocess and return output."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        f.flush()
        try:
            result = subprocess.run(
                [sys.executable, f.name],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            output = result.stdout
            if result.returncode != 0:
                output += result.stderr
            return output
        except subprocess.TimeoutExpired:
            return "Error: Execution timed out"
        finally:
            os.unlink(f.name)


if __name__ == "__main__":
    print(execute_python("print('Hello from subprocess!')"))
