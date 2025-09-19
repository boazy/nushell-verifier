from typing import List
from .models import ScriptAnalysis


class Reporter:
    """Reporter for generating compatibility analysis reports."""

    def __init__(self, verbose: bool = False):
        """Initialize reporter with verbosity setting."""
        self.verbose = verbose

    def generate_report(self, analyses: List[ScriptAnalysis]) -> None:
        """Generate and display compatibility report."""
        if not analyses:
            print("No scripts analyzed.")
            return

        compatible_count = sum(1 for a in analyses if a.is_compatible)
        total_count = len(analyses)

        print(f"\n{'='*60}")
        print("NUSHELL COMPATIBILITY REPORT")
        print(f"{'='*60}")
        print(f"Total scripts: {total_count}")
        print(f"Compatible: {compatible_count}")
        print(f"Issues found: {total_count - compatible_count}")
        print(f"Target version: {analyses[0].target_version if analyses else 'Unknown'}")

        # Group analyses by compatibility
        compatible_scripts = [a for a in analyses if a.is_compatible]
        incompatible_scripts = [a for a in analyses if not a.is_compatible]

        # Report incompatible scripts first
        if incompatible_scripts:
            print(f"\n{'⚠️  SCRIPTS WITH COMPATIBILITY ISSUES':<60}")
            print(f"{'-'*60}")

            for analysis in incompatible_scripts:
                self._report_script_issues(analysis)

        # Report compatible scripts if verbose
        if self.verbose and compatible_scripts:
            print(f"\n{'✅ COMPATIBLE SCRIPTS':<60}")
            print(f"{'-'*60}")

            for analysis in compatible_scripts:
                self._report_compatible_script(analysis)

        # Summary
        print(f"\n{'='*60}")
        if incompatible_scripts:
            print(f"❌ {len(incompatible_scripts)} script(s) need attention")
            print("Review the issues above and apply suggested fixes.")
        else:
            print("✅ All scripts are compatible!")

        if compatible_count > 0:
            print(f"✅ {compatible_count} script(s) are up to date")

    def _report_script_issues(self, analysis: ScriptAnalysis) -> None:
        """Report issues for a single script."""
        script_name = analysis.script.path.name
        relative_path = str(analysis.script.path)

        print(f"\n📄 {script_name}")
        print(f"   Path: {relative_path}")
        print(f"   Last compatible: {analysis.script.compatible_version}")
        print(f"   Method: {analysis.script.method.value}")

        # Group issues by severity
        errors = [i for i in analysis.issues if i.severity == "error"]
        warnings = [i for i in analysis.issues if i.severity == "warning"]
        info = [i for i in analysis.issues if i.severity == "info"]

        for severity, issues in [("ERROR", errors), ("WARNING", warnings), ("INFO", info)]:
            if issues:
                for i, issue in enumerate(issues, 1):
                    icon = "🔴" if severity == "ERROR" else "🟡" if severity == "WARNING" else "🔵"
                    print(f"   {icon} {severity} {i}: {issue.description}")
                    if issue.suggested_fix:
                        print(f"      💡 Fix: {issue.suggested_fix}")

    def _report_compatible_script(self, analysis: ScriptAnalysis) -> None:
        """Report a compatible script."""
        script_name = analysis.script.path.name
        print(f"✅ {script_name} (compatible with {analysis.target_version})")

        if self.verbose:
            print(f"   Path: {analysis.script.path}")
            print(f"   Method: {analysis.script.method.value}")