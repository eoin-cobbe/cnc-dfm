from __future__ import annotations

import os
import re
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


def print_part_process_data(data: PartProcessData) -> None:
    print(f"{paint('MATERIAL', Ansi.BOLD, Ansi.BLUE)}  {data.material_label}")
    print(
        f"{paint('PART BBOX', Ansi.BOLD, Ansi.BLUE)}  "
        f"{data.part_bbox_x_mm:.2f} x {data.part_bbox_y_mm:.2f} x {data.part_bbox_z_mm:.2f} mm"
    )
    print(
        f"{paint('STOCK BBOX (+10/axis)', Ansi.BOLD, Ansi.BLUE)}  "
        f"{data.stock_bbox_x_mm:.2f} x {data.stock_bbox_y_mm:.2f} x {data.stock_bbox_z_mm:.2f} mm"
    )
    print(f"{paint('VOLUME', Ansi.BOLD, Ansi.BLUE)}  {data.volume_mm3:.2f} mm^3")
    print(f"{paint('STOCK VOLUME', Ansi.BOLD, Ansi.BLUE)}  {data.stock_volume_mm3:.2f} mm^3")
    print(f"{paint('REMOVED VOLUME', Ansi.BOLD, Ansi.BLUE)}  {data.removed_volume_mm3:.2f} mm^3")
    print(f"{paint('PART SURFACE AREA', Ansi.BOLD, Ansi.BLUE)}  {data.part_surface_area_mm2:.2f} mm^2")
    print(f"{paint('PART SA/V', Ansi.BOLD, Ansi.BLUE)}  {data.part_sav_ratio:.6f} 1/mm")
    print(f"{paint('BBOX SA/V', Ansi.BOLD, Ansi.BLUE)}  {data.bbox_sav_ratio:.6f} 1/mm")
    print(f"{paint('SURFACE COMPLEXITY', Ansi.BOLD, Ansi.BLUE)}  {data.surface_complexity_ratio:.3f}x")
    print(f"{paint('FINISH MULTIPLIER', Ansi.BOLD, Ansi.BLUE)}  {data.finish_multiplier:.3f}x")
    print(f"{paint('MASS', Ansi.BOLD, Ansi.BLUE)}  {data.mass_kg:.4f} kg")
    print(f"{paint('STOCK MASS', Ansi.BOLD, Ansi.BLUE)}  {data.stock_mass_kg:.4f} kg")
    print(
        f"{paint('BILLET COST', Ansi.BOLD, Ansi.BLUE)}  "
        f"{data.material_billet_cost_eur_per_kg:.2f} EUR/kg"
    )
    print(f"{paint('MATERIAL FIXED COST', Ansi.BOLD, Ansi.BLUE)}  {data.material_fixed_cost_eur:.2f} EUR")
    print(f"{paint('STOCK MATERIAL COST', Ansi.BOLD, Ansi.BLUE)}  {data.material_stock_cost_eur:.2f} EUR")
    print(f"{paint('SETUP DIRECTIONS', Ansi.BOLD, Ansi.BLUE)}  {data.required_setup_directions}")
    print(f"{paint('MACHINE TYPE', Ansi.BOLD, Ansi.BLUE)}  {data.machine_type}")
    print(f"{paint('HOLE COUNT', Ansi.BOLD, Ansi.BLUE)}  {data.hole_count}")
    print(f"{paint('HOLE MULTIPLIER', Ansi.BOLD, Ansi.BLUE)}  {data.hole_count_multiplier:.3f}x")
    print(f"{paint('RADIUS COUNT', Ansi.BOLD, Ansi.BLUE)}  {data.radius_count}")
    print(f"{paint('RADIUS MULTIPLIER', Ansi.BOLD, Ansi.BLUE)}  {data.radius_count_multiplier:.3f}x")
    print(f"{paint('MACHINABILITY', Ansi.BOLD, Ansi.BLUE)}  {data.machinability_percent:.1f}%")
    print(
        f"{paint('BASELINE 6061 MRR', Ansi.BOLD, Ansi.BLUE)}  "
        f"{data.baseline_6061_mrr_mm3_per_min:.2f} mm^3/min"
    )
    print(
        f"{paint('EST. ROUGHING MRR', Ansi.BOLD, Ansi.BLUE)}  "
        f"{data.estimated_roughing_mrr_mm3_per_min:.2f} mm^3/min"
    )
    print(f"{paint('MATERIAL MULTIPLIER', Ansi.BOLD, Ansi.BLUE)}  {data.material_time_multiplier:.3f}x")
    print(f"{paint('RULE MULTIPLIER', Ansi.BOLD, Ansi.BLUE)}  {data.rule_multiplier:.3f}x")
    print(f"{paint('TOTAL TIME MULT', Ansi.BOLD, Ansi.BLUE)}  {data.total_time_multiplier:.3f}x")
    print(f"{paint('QTY', Ansi.BOLD, Ansi.BLUE)}  {data.qty}")
    print(f"{paint('QTY MULTIPLIER', Ansi.BOLD, Ansi.BLUE)}  {data.qty_multiplier:.3f}x")
    print(f"{paint('ROUGHING TIME', Ansi.BOLD, Ansi.BLUE)}  {data.roughing_time_min:.2f} min")
    print(f"{paint('BASE MACHINING TIME', Ansi.BOLD, Ansi.BLUE)}  {data.base_machining_time_min:.2f} min")
    print(f"{paint('MACHINING TIME', Ansi.BOLD, Ansi.BLUE)}  {data.machining_time_min:.2f} min")
    print(f"{paint('MACHINE RATE', Ansi.BOLD, Ansi.BLUE)}  {data.machine_hourly_rate_eur:.2f} EUR/hr")
    print(f"{paint('ROUGHING COST', Ansi.BOLD, Ansi.BLUE)}  {data.roughing_cost:.2f} EUR")
    print(f"{paint('MACHINING COST', Ansi.BOLD, Ansi.BLUE)}  {data.machining_cost:.2f} EUR")
    print(f"{paint('UNIT EST. COST', Ansi.BOLD, Ansi.BLUE)}  {data.total_estimated_cost_eur:.2f} EUR")
    print(f"{paint('BATCH EST. COST', Ansi.BOLD, Ansi.BLUE)}  {data.batch_total_estimated_cost_eur:.2f} EUR")
    print(f"{paint('BILLET COST SOURCE', Ansi.DIM)}  {data.material_billet_cost_source}")
    print(f"{paint('MATERIAL FIXED SOURCE', Ansi.DIM)}  {data.material_fixed_cost_source}")
    print(f"{paint('MACHINABILITY SOURCE', Ansi.DIM)}  {data.machinability_source}")
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
