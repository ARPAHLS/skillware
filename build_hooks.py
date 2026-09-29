## Copy examples/README.md into the package so it is included in the wheel.
from pathlib import Path
from setuptools.command.build_py import build_py

class CustomBuildPy(build_py):
    def run(self):
        super().run()
        source_path = Path(__file__).parent / "examples" / "README.md"
        target_path = Path(self.build_lib) / "skillware" / "resources" / "examples" / "README.md"
        self.mkpath(target_path.parent)
        self.copy_file(source_path, target_path)
