import json
import os
import re
import subprocess
from typing import Any, Dict


class BadgeGenerator:
    """
    Generates dynamic quality badges for the README.md
    """

    def create_coverage_badge(self, data: Dict[str, Any]) -> str:
        pct = data.get("totals", {}).get("percent_covered", 0)
        color = "red"
        if pct >= 80:
            color = "brightgreen"
        elif pct >= 60:
            color = "yellow"

        return f"![Coverage](https://img.shields.io/badge/coverage-{int(pct)}%25-{color})"

    def create_ruff_badge(self, error_count: int) -> str:
        if error_count == 0:
            return "![Lint](https://img.shields.io/badge/ruff-passing-brightgreen)"
        return f"![Lint](https://img.shields.io/badge/ruff-{error_count}_errors-red)"

    def create_mypy_badge(self, passing: bool) -> str:
        if passing:
            return "![Types](https://img.shields.io/badge/mypy-passing-brightgreen)"
        return "![Types](https://img.shields.io/badge/mypy-failing-red)"

    def create_version_badge(self, version: str) -> str:
        return f"![Version](https://img.shields.io/badge/version-{version}-blue)"

    def create_license_badge(self, license_name: str) -> str:
        return f"![License](https://img.shields.io/badge/license-{license_name}-lightgrey)"

    def get_version(self) -> str:
        try:
            with open("pyproject.toml", "r") as f:
                content = f.read()
                match = re.search(r'version\s*=\s*"([^"]+)"', content)
                return match.group(1) if match else "unknown"
        except Exception:
            return "unknown"

    def run_ruff(self) -> int:
        res = subprocess.run(["ruff", "check", "."], capture_output=True, text=True)
        # Ruff output usually looks like "Found X errors"
        match = re.search(r"Found (\d+) error", res.stdout)
        if match:
            return int(match.group(1))
        return 0 if res.returncode == 0 else 1

    def run_mypy(self) -> bool:
        res = subprocess.run(["mypy", "."], capture_output=True, text=True)
        return res.returncode == 0

    def generate_all(self):
        # 1. Run Tests and Coverage
        subprocess.run(
            ["pytest", "--cov=src/zotero_cli", "--cov-report=json", "tests/unit"],
            capture_output=True,
        )
        coverage_file = "coverage.json"
        if not os.path.exists(coverage_file):
            print("Error: coverage.json not found.")
            return

        with open(coverage_file, "r") as f:
            cov_data = json.load(f)

        # 2. Run Quality Checks
        ruff_errors = self.run_ruff()
        mypy_ok = self.run_mypy()
        version = self.get_version()

        badges = [
            self.create_version_badge(version),
            self.create_coverage_badge(cov_data),
            self.create_ruff_badge(ruff_errors),
            self.create_mypy_badge(mypy_ok),
            self.create_license_badge("MIT"),
            "![Python](https://img.shields.io/badge/python-3.10+-blue)",
        ]

        badge_section = " ".join(badges)
        self.update_readme(badge_section)
        print("Badges generated and README.md updated.")

    def update_readme(self, badge_section: str):
        readme_path = "README.md"
        with open(readme_path, "r") as f:
            content = f.read()

        # Look for existing badge section or top of file
        # We'll use a marker approach
        marker_start = "<!-- BADGES_START -->"
        marker_end = "<!-- BADGES_END -->"

        new_content = f"{marker_start}\n{badge_section}\n{marker_end}"

        if marker_start in content and marker_end in content:
            pattern = re.compile(rf"{marker_start}.*?{marker_end}", re.DOTALL)
            content = pattern.sub(new_content, content)
        else:
            # Prepend to top
            content = f"{new_content}\n\n{content}"

        with open(readme_path, "w") as f:
            f.write(content)


if __name__ == "__main__":
    gen = BadgeGenerator()
    gen.generate_all()
