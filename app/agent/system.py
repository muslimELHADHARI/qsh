import platform


def system_info() -> dict[str, str]:
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
    }
