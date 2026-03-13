from __future__ import annotations

import os
import re
import shutil
from collections import OrderedDict
from typing import List

from dfm_models import PartProcessData, Recommendation, RuleResult


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


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


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
        " ######  ##    ##  ######         #######   ######## ##     ## ",
        "##    ## ###   ## ##    ##        ##    ##  ##       ###   ### ",
        "##       ####  ## ##              ##    ##  ##       #### #### ",
        "##       ## ## ## ##              ##    ##  ######   ## ### ## ",
        "##       ##  #### ##              ##    ##  ##       ##  #  ## ",
        "##    ## ##   ### ##    ##        ##    ##  ##       ##     ## ",
        " ######  ##    ##  ######         #######   ##       ##     ## ",
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
    def _visible_len(text: str) -> int:
        return len(ANSI_RE.sub("", text))

    def _pad_visible(text: str, width: int) -> str:
        return text + (" " * max(0, width - _visible_len(text)))

    term_width = shutil.get_terminal_size((120, 24)).columns
    content_width = max(60, term_width - 2)
    col_width = max(28, (content_width - gap) // 2)
    for i in range(0, len(rows), 2):
        left_label, left_value = rows[i]
        left_raw = f"{left_label:<{label_width}} {left_value}"
        if i + 1 < len(rows):
            right_label, right_value = rows[i + 1]
            right_raw = f"{right_label:<{label_width}} {right_value}"
            if _visible_len(left_raw) <= col_width and _visible_len(right_raw) <= col_width:
                print(f"  {_pad_visible(left_raw, col_width)}{' ' * gap}{_pad_visible(right_raw, col_width)}")
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
            ("SURFACE AREA", f"{data.surface_area_ratio:.3f}x"),
            ("SURFACE COMPLEXITY", f"{data.surface_complexity_faces} faces"),
            ("HOLE COUNT", str(data.hole_count)),
            ("INTERNAL RADIUS COUNT", str(data.radius_count)),
            ("MACHINABILITY INDEX (6061=1.0)", f"{data.machinability_index:.3f}"),
            ("BASELINE 6061 MRR", f"{data.baseline_6061_mrr_mm3_per_min:.2f} mm^3/min"),
            ("EST. ROUGHING MRR", f"{data.estimated_roughing_mrr_mm3_per_min:.2f} mm^3/min"),
        ],
    )
    _print_section(
        "MULTIPLIERS",
        [
            ("SURFACE AREA MULTIPLIER", f"{data.surface_area_multiplier:.3f}x"),
            ("COMPLEXITY MULTIPLIER", f"{data.complexity_multiplier:.3f}x"),
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
            ("ROUGHING TIME (PRE QTY)", f"{data.roughing_time_min:.2f} min"),
            ("MACHINING TIME (PRE QTY)", f"{data.machining_time_min:.2f} min"),
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


def _recommendation_tag(kind: str) -> str:
    if kind == "blocker":
        return paint("BLOCKER", Ansi.BOLD, Ansi.RED)
    if kind == "cost":
        return paint("COST", Ansi.BOLD, Ansi.YELLOW)
    return paint("INFO", Ansi.BOLD, Ansi.GREEN)


def _format_currency_range(minimum: float, maximum: float) -> str:
    if abs(minimum - maximum) <= 0.005:
        return f"{maximum:.2f} EUR"
    return f"{minimum:.2f}-{maximum:.2f} EUR"


def _format_percent_range(minimum: float, maximum: float) -> str:
    if abs(minimum - maximum) <= 0.05:
        return f"{maximum:.1f}%"
    return f"{minimum:.1f}-{maximum:.1f}%"


def print_recommendations(recommendations: List[Recommendation]) -> None:
    print(f"{paint('RECOMMENDATIONS', Ansi.BOLD, Ansi.BLUE)}")
    if not recommendations:
        print("  None")
        print("")
        return

    for idx, recommendation in enumerate(recommendations, start=1):
        print(
            f"  {idx}. {_recommendation_tag(recommendation.kind)}  "
            f"{paint(recommendation.title, Ansi.BOLD)}  "
            f"{paint(f'P{recommendation.priority}', Ansi.DIM)}"
        )
        print(f"     {recommendation.summary}")
        if recommendation.cost_impact is not None:
            print(
                "     "
                f"{paint('SAVE', Ansi.BOLD, Ansi.GREEN)}  "
                f"{_format_currency_range(recommendation.cost_impact.minimum_unit_savings_eur, recommendation.cost_impact.maximum_unit_savings_eur)} / unit  "
                f"{_format_currency_range(recommendation.cost_impact.minimum_batch_savings_eur, recommendation.cost_impact.maximum_batch_savings_eur)} / batch  "
                f"({_format_percent_range(recommendation.cost_impact.minimum_percent_savings, recommendation.cost_impact.maximum_percent_savings)})"
            )
        if recommendation.feature_insights:
            print(f"     {paint('WHERE', Ansi.BOLD, Ansi.CYAN)}")
            grouped_insights: "OrderedDict[str, int]" = OrderedDict()
            for insight in recommendation.feature_insights:
                grouped_insights[insight.summary] = grouped_insights.get(insight.summary, 0) + 1
            for summary, count in grouped_insights.items():
                prefix = f"x{count} " if count > 1 else ""
                detail = ""
                matching = [insight for insight in recommendation.feature_insights if insight.summary == summary and insight.cost_impact is not None]
                if matching:
                    detail = (
                        "  "
                        f"[save {_format_currency_range(matching[0].cost_impact.minimum_unit_savings_eur, matching[0].cost_impact.maximum_unit_savings_eur)} / unit]"
                    )
                print(f"       - {prefix}{summary}{detail}")
        print(f"     {paint('IMPACT', Ansi.BOLD, Ansi.YELLOW)}  {recommendation.impact}")
        if recommendation.cost_impact is not None:
            print(f"     {paint('WHY', Ansi.BOLD, Ansi.CYAN)}  {recommendation.cost_impact.rationale}")
            print(
                f"     {paint('RANGE', Ansi.DIM)}  "
                f"{recommendation.cost_impact.conservative_label} -> {recommendation.cost_impact.optimistic_label}"
            )
            for row in recommendation.cost_impact.direct_breakdown:
                print(
                    "     "
                    f"{paint('DIRECT', Ansi.DIM)}  {row.label}: "
                    f"{_format_currency_range(row.minimum_unit_savings_eur, row.maximum_unit_savings_eur)} / unit"
                )
                if row.details:
                    print(f"             {row.details}")
            for row in recommendation.cost_impact.linked_breakdown:
                print(
                    "     "
                    f"{paint('LINKED', Ansi.DIM)}  {row.label}: "
                    f"{_format_currency_range(row.minimum_unit_savings_eur, row.maximum_unit_savings_eur)} / unit"
                )
                if row.details:
                    print(f"             {row.details}")
        for action in recommendation.actions:
            print(f"     - {action}")
        print(f"     {paint('SOURCE', Ansi.DIM)}  {recommendation.source}")
        print("")


def print_report(results: List[RuleResult], file_path: str, recommendations: List[Recommendation] | None = None) -> None:
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
    if recommendations is not None:
        print_recommendations(recommendations)
        print(paint("-" * 72, Ansi.GRAY))
    passed_count = sum(1 for r in results if r.passed)
    overall_pass = passed_count == len(results)
    print(
        f"{paint('SUMMARY', Ansi.BOLD, Ansi.BLUE)}  "
        f"{passed_count}/{len(results)} passed  "
        f"{status_text(overall_pass)}"
    )
    print("")
