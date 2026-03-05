from __future__ import annotations

import os
import re
from typing import List

from dfm_models import RuleResult


class Ansi:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    CYAN = "\033[36m"
    BLUE = "\033[34m"
    GRAY = "\033[90m"


def use_color() -> bool:
    return os.getenv("TERM") is not None and os.getenv("NO_COLOR") is None


def paint(text: str, *styles: str) -> str:
    if not use_color():
        return text
    return f"{''.join(styles)}{text}{Ansi.RESET}"


def status_text(passed: bool) -> str:
    return paint("PASS", Ansi.BOLD, Ansi.GREEN) if passed else paint("FAIL", Ansi.BOLD, Ansi.RED)


def icon(passed: bool) -> str:
    return paint("OK", Ansi.GREEN) if passed else paint("XX", Ansi.RED)


def print_block_logo() -> None:
    lines = [
        " ######  ##    ##  ######          ######   ######## ##     ## ",
        "##    ## ###   ## ##    ##        ##    ##  ##       ###   ### ",
        "##       ####  ## ##              ##    ##  ##       #### #### ",
        "##       ## ## ## ##              ##    ##  ######   ## ### ## ",
        "##       ##  #### ##              ##    ##  ##       ##  #  ## ",
        "##    ## ##   ### ##    ##        ##    ##  ##       ##     ## ",
        " ######  ##    ##  ######          ######   ##       ##     ## ",
    ]
    for line in lines:
        print(paint(line, Ansi.BOLD, Ansi.CYAN))


def print_boot(step_file: str) -> None:
    print("")
    print("")
    print_block_logo()
    print("")
    print("")
    print("")


def print_report(results: List[RuleResult], file_path: str) -> None:
    print(f"{paint('FILE', Ansi.BOLD, Ansi.BLUE)}  {file_path}")
    print(paint("-" * 72, Ansi.GRAY))

    for idx, result in enumerate(results, start=1):
        match = re.search(r"Rule\s+(\d+)", result.name)
        label = f"R{match.group(1)}" if match else f"R{idx}"
        print(f"{icon(result.passed)}  {paint(label, Ansi.BOLD, Ansi.CYAN)}  {result.name}")
        print(f"    {paint('RESULT', Ansi.BOLD)}  {status_text(result.passed)}")
        print(
            f"    {paint('FEATURES', Ansi.DIM)} "
            f"total={result.detected_features} "
            f"pass={result.passed_features} "
            f"fail={result.failed_features}"
        )
        if result.axis_breakdown is not None:
            for axis in ("X", "Y", "Z"):
                if axis not in result.axis_breakdown:
                    continue
                detected, passed, failed = result.axis_breakdown[axis]
                print(
                    f"             {axis}: "
                    f"detected={detected} pass={passed} fail={failed}"
                )
        if result.minimum_detected is not None or result.required_minimum is not None:
            min_text = (
                f"{result.minimum_detected:.3f} mm"
                if result.minimum_detected is not None
                else "N/A"
            )
            req_text = (
                f"{result.required_minimum:.3f} mm"
                if result.required_minimum is not None
                else "N/A"
            )
            print(f"    {paint('MINIMUM DETECTED', Ansi.DIM)}  {min_text}")
            print(f"    {paint('REQUIRED MINIMUM', Ansi.DIM)}  {req_text}")
        else:
            print(f"    {paint('DETAIL', Ansi.DIM)}   {result.details}")
        print("")

    print(paint("-" * 72, Ansi.GRAY))
    passed_count = sum(1 for r in results if r.passed)
    overall_pass = passed_count == len(results)
    print(
        f"{paint('SUMMARY', Ansi.BOLD, Ansi.BLUE)}  "
        f"{passed_count}/{len(results)} passed  "
        f"{status_text(overall_pass)}"
    )
