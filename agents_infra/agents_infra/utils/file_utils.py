import codecs
import os


def ensure_directory_exists(path):
    """Ensure the parent directory for the given file path exists."""
    os.makedirs(os.path.dirname(path), exist_ok=True)


def write_to_file(path, content):
    """Write content to a file."""
    ensure_directory_exists(path)
    with codecs.open(path, 'w', encoding='utf-8') as f:
        f.write(content)


def read_from_file(path):
    """Read and return the content of a file."""
    if os.path.exists(path):
        with codecs.open(path, 'w', encoding='utf-8') as f:
            return f.read().strip()
    return None
