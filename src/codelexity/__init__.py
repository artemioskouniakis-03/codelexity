from importlib.metadata import PackageNotFoundError, version

# Read from installed metadata so pyproject.toml stays the only place the version is written.
try:
    __version__ = version("codelexity")
except PackageNotFoundError:  # running from a source checkout that was never installed
    __version__ = "0.0.0.dev0"
