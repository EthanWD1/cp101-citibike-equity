"""Execute the notebook in a fresh kernel using this interpreter and no external network."""
import os
import sys
import nbformat
from nbclient import NotebookClient
from jupyter_client import KernelManager


def execute():
    os.environ["CP101_OFFLINE"] = "1"
    os.environ.setdefault("JUPYTER_PLATFORM_DIRS", "1")
    os.environ.setdefault("IPYTHONDIR", ".cache/ipython")
    path = "notebooks/midterm_analysis.ipynb"
    notebook = nbformat.read(path, as_version=4)
    manager = KernelManager(kernel_name="python3")
    manager.kernel_spec.argv = [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"]
    client = NotebookClient(notebook, km=manager, timeout=1800, resources={"metadata": {"path": "notebooks"}})
    try:
        client.execute()
    finally:
        if manager.has_kernel:
            manager.shutdown_kernel(now=True)
    nbformat.write(notebook, path)
    print("Fresh-kernel execution succeeded with external network disabled.")


if __name__ == "__main__":
    execute()
