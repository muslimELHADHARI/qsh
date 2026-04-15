import base64
from pathlib import Path


def read_file_b64(path: str) -> str:
    return base64.b64encode(Path(path).read_bytes()).decode("ascii")


def write_file_b64(path: str, content_b64: str) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(base64.b64decode(content_b64.encode("ascii")))
