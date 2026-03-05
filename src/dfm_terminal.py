from __future__ import annotations

import os
import re
import shutil
from typing import List

from dfm_models import PartProcessData, RuleResult


class Ansi:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    CYAN = "\033[36m"
    BLUE = "\033[34m"
    YELLOW = "\033[33m"
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


def _print_two_column_rows(rows: List[tuple[str, str]], label_width: int = 24, gap: int = 4) -> None:
    term_width = shutil.get_terminal_size((120, 24)).columns
    content_width = max(60, term_width - 2)
    col_width = max(28, (content_width - gap) // 2)
    for i in range(0, len(rows), 2):
        left_label, left_value = rows[i]
        left_raw = f"{left_label:<{label_width}} {left_value}"
        if i + 1 < len(rows):
            right_label, right_value = rows[i + 1]
            right_raw = f"{right_label:<{label_width}} {right_value}"
            if len(left_raw) <= col_width and len(right_raw) <= col_width:
                print(f"  {left_raw.ljust(col_width)}{' ' * gap}{right_raw.ljust(col_width)}")
            else:
                print(f"  {left_raw}")
                print(f"  {right_raw}")
        else:
            print(f"  {left_raw}")


def _print_single_column_rows(rows: List[tuple[str, str]], label_width: int = 38) -> None:
    for label, value in rows:
        print(f"  {label:<{label_width}} {value}")


def _print_section(title: str, rows: List[tuple[str, str]]) -> None:
    print(f"{paint(title, Ansi.BOLD, Ansi.BLUE)}")
    _print_two_column_rows(rows)
    print("")


def print_part_process_data(data: PartProcessData) -> None:
    _print_section(
        "FACTS",
        [
            ("MATERIAL", data.material_label),
            ("MACHINE TYPE", data.machine_type),
            (
                "PART BBOX",
                f"{data.part_bbox_x_mm:.2f} x {data.part_bbox_y_mm:.2f} x {data.part_bbox_z_mm:.2f} mm",
            ),
            (
                "STOCK BBOX (+10/axis)",
                f"{data.stock_bbox_x_mm:.2f} x {data.stock_bbox_y_mm:.2f} x {data.stock_bbox_z_mm:.2f} mm",
            ),
            ("VOLUME", f"{data.volume_mm3:.2f} mm^3"),
            ("STOCK VOLUME", f"{data.stock_volume_mm3:.2f} mm^3"),
            ("REMOVED VOLUME", f"{data.removed_volume_mm3:.2f} mm^3"),
            ("PART SURFACE AREA", f"{data.part_surface_area_mm2:.2f} mm^2"),
            ("PART SA/V", f"{data.part_sav_ratio:.6f} 1/mm"),
            ("BBOX SA/V", f"{data.bbox_sav_ratio:.6f} 1/mm"),
            ("MASS", f"{data.mass_kg:.4f} kg"),
            ("STOCK MASS", f"{data.stock_mass_kg:.4f} kg"),
            ("SETUP DIRECTIONS", data.required_setup_directions),
            ("QTY", str(data.qty)),
        ],
    )
    _print_section(
        "PRE-MULTIPLIER DRIVERS",
        [
            ("SURFACE COMPLEXITY", f"{data.surface_complexity_ratio:.3f}x"),
            ("HOLE COUNT", str(data.hole_count)),
            ("RADIUS COUNT", str(data.radius_count)),
            ("MACHINABILITY", f"{data.machinability_percent:.1f}%"),
            ("BASELINE 6061 MRR", f"{data.baseline_6061_mrr_mm3_per_min:.2f} mm^3/min"),
            ("EST. ROUGHING MRR", f"{data.estimated_roughing_mrr_mm3_per_min:.2f} mm^3/min"),
        ],
    )
    _print_section(
        "MULTIPLIERS",
        [
            ("FINISH MULTIPLIER", f"{data.finish_multiplier:.3f}x"),
            ("HOLE MULTIPLIER", f"{data.hole_count_multiplier:.3f}x"),
            ("RADIUS MULTIPLIER", f"{data.radius_count_multiplier:.3f}x"),
            ("MATERIAL MULTIPLIER", f"{data.material_time_multiplier:.3f}x"),
            ("RULE MULTIPLIER", f"{data.rule_multiplier:.3f}x"),
            ("TOTAL TIME MULT", paint(f"{data.total_time_multiplier:.3f}x", Ansi.BOLD)),
            ("QTY MULTIPLIER", f"{data.qty_multiplier:.3f}x"),
        ],
    )
    _print_section(
        "POST-MULTIPLIER OUTPUTS",
        [
            ("ROUGHING TIME", f"{data.roughing_time_min:.2f} min"),
            ("BASE MACHINING TIME", f"{data.base_machining_time_min:.2f} min"),
            ("MACHINING TIME", f"{data.machining_time_min:.2f} min"),
            ("MACHINE RATE", f"{data.machine_hourly_rate_eur:.2f} EUR/hr"),
        ],
    )
    print(f"{paint('COSTS', Ansi.BOLD, Ansi.BLUE)}")
    _print_single_column_rows(
        [
            ("RAW MATERIAL RATE", f"{data.material_billet_cost_eur_per_kg:.2f} EUR/kg"),
            ("MATERIAL BASE FEE (PER PART - PRE QTY)", f"{data.material_fixed_cost_eur:.2f} EUR"),
            ("MATERIAL TOTAL (PER PART - PRE QTY)", f"{data.material_stock_cost_eur:.2f} EUR"),
            ("UNIT EST. COST", f"{data.total_estimated_cost_eur:.2f} EUR"),
            ("BATCH EST. COST", f"{data.batch_total_estimated_cost_eur:.2f} EUR"),
        ]
    )
    print("")

    print(paint("-" * 72, Ansi.GRAY))


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _build_rule_bar(avg: float, threshold: float, threshold_kind: str, width: int = 36) -> str:
    upper = max(threshold * 2.0, avg * 1.2, 1.0)
    t_pos = int(round((_clamp01(threshold / upper)) * (width - 1)))
    a_pos = int(round((_clamp01(avg / upper)) * (width - 1)))
    chars = ["-"] * width
    chars[t_pos] = "T"
    chars[a_pos] = "A" if a_pos != t_pos else "*"
    core = "".join(chars)
    if threshold_kind == "min":
        return f"[{core}] min-ok>=T"
    return f"[{core}] max-ok<=T"


def print_report(results: List[RuleResult], file_path: str) -> None:
    print(f"{paint('FILE', Ansi.BOLD, Ansi.BLUE)}  {file_path}")
    print(paint("-" * 72, Ansi.GRAY))

    for idx, result in enumerate(results, start=1):
        match = re.search(r"Rule\s+(\d+)", result.name)
        label = f"R{match.group(1)}" if match else f"R{idx}"
        print(f"{icon(result.passed)}  {paint(label, Ansi.BOLD, Ansi.CYAN)}  {result.name}")
        print(f"    {paint('RESULT', Ansi.BOLD)}  {status_text(result.passed)}")
        print(f"    {paint('RULE MULTIPLIER', Ansi.BOLD, Ansi.YELLOW)}  {result.rule_multiplier:.3f}x")
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
        if (
            result.metric_label is not None
            and result.average_detected is not None
            and result.threshold is not None
            and result.threshold_kind in ("min", "max")
        ):
            bar = _build_rule_bar(result.average_detected, result.threshold, result.threshold_kind)
            print(
                f"    {paint('METRIC BAR', Ansi.BOLD, Ansi.YELLOW)}  "
                f"{paint(bar, Ansi.BOLD, Ansi.CYAN)}"
            )
            print(
                f"               {result.metric_label}: "
                f"avg={result.average_detected:.3f} "
                f"threshold={result.threshold:.3f}"
            )
        print("")

    print(paint("-" * 72, Ansi.GRAY))
    passed_count = sum(1 for r in results if r.passed)
    overall_pass = passed_count == len(results)
    print(
        f"{paint('SUMMARY', Ansi.BOLD, Ansi.BLUE)}  "
        f"{passed_count}/{len(results)} passed  "
        f"{status_text(overall_pass)}"
    )
