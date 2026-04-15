import subprocess


def execute_shell(command: str, timeout: int = 20) -> dict[str, str | int]:
    completed = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
    return {
        "return_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
