from __future__ import annotations

import re
import uuid
from typing import Dict, List, Sequence

from dfm_models import FeatureCandidate, OffenderRecord, RemediationProposal

UNIT_RE = re.compile(r"^\s*-?\d+(?:\.\d+)?\s*(.*)$")


def _expr_with_same_unit(before: str, new_value: float) -> str:
    match = UNIT_RE.match(before or "")
    suffix = match.group(1).strip() if match else ""
    number = f"{new_value:.3f}".rstrip("0").rstrip(".")
    return f"{number} {suffix}".strip()


def _proposal(
    offender: OffenderRecord,
    candidate: FeatureCandidate,
    *,
    new_value: float,
    rationale: str,
    expected_effect: str,
    action: str,
    matched_offender_index: int,
) -> RemediationProposal:
    return RemediationProposal(
        proposal_id=uuid.uuid4().hex[:12],
        rule_id=offender.rule_id,
        feature_id=candidate.feature_id,
        feature_type=candidate.feature_type,
        parameter_path=candidate.parameter_path,
        before=candidate.current_expression,
        after=_expr_with_same_unit(candidate.current_expression, new_value),
        rationale=rationale,
        expected_effect=expected_effect,
        confidence=candidate.confidence,
        requires_confirmation=True,
        matched_offender_index=matched_offender_index,
        parameter_id=candidate.parameter_id,
        action=action,
        meta={"target_numeric_value": new_value, **candidate.meta},
    )


def build_proposals(
    offenders: Sequence[OffenderRecord],
    matches: Dict[int, List[FeatureCandidate]],
) -> List[RemediationProposal]:
    proposals: List[RemediationProposal] = []
    for idx, offender in enumerate(offenders):
        candidates = matches.get(idx, [])
        if offender.rule_id == "R4":
            grouped: Dict[str, List[FeatureCandidate]] = {"depth": [], "diameter": []}
            for candidate in candidates:
                label = (candidate.parameter_id or "").lower()
                if candidate.feature_type != "hole" or not candidate.editable:
                    continue
                if "depth" in label:
                    grouped["depth"].append(candidate)
                elif "diameter" in label:
                    grouped["diameter"].append(candidate)
            for label, rows in grouped.items():
                if not rows:
                    continue
                best = rows[0]
                runner_up = rows[1] if len(rows) > 1 else None
                if best.confidence < 0.65:
                    continue
                if runner_up is not None and (best.confidence - runner_up.confidence) < 0.12:
                    continue
                if label == "depth":
                    proposals.append(
                        _proposal(
                            offender,
                            best,
                            new_value=float(offender.meta.get("target_depth_mm", offender.current_value)),
                            rationale="Reduce blind-hole depth to satisfy the depth/diameter limit.",
                            expected_effect="Rule 4 should improve without enlarging the hole.",
                            action="reduce_depth",
                            matched_offender_index=idx,
                        )
                    )
                else:
                    proposals.append(
                        _proposal(
                            offender,
                            best,
                            new_value=float(offender.meta.get("target_diameter_mm", offender.current_value)),
                            rationale="Increase hole diameter to satisfy the depth/diameter limit.",
                            expected_effect="Rule 4 should improve while keeping the same hole depth.",
                            action="increase_diameter",
                            matched_offender_index=idx,
                        )
                    )
            continue

        if not candidates:
            continue
        candidate = candidates[0]
        runner_up = candidates[1] if len(candidates) > 1 else None
        if candidate.confidence < 0.65:
            continue
        if runner_up is not None and (candidate.confidence - runner_up.confidence) < 0.12:
            continue
        if not candidate.editable or not offender.auto_remediable:
            continue
        if offender.rule_id == "R1":
            proposals.append(
                _proposal(
                    offender,
                    candidate,
                    new_value=offender.target_value,
                    rationale="Increase the fillet radius to meet the rule target.",
                    expected_effect="Rule 1 should pass for the mapped corner set.",
                    action="increase_radius",
                    matched_offender_index=idx,
                )
            )
        elif offender.rule_id == "R2":
            proposals.append(
                _proposal(
                    offender,
                    candidate,
                    new_value=float(offender.meta.get("target_depth_mm", offender.target_value)),
                    rationale="Reduce blind-extrude depth to bring the pocket ratio back under the threshold.",
                    expected_effect="Rule 2 should improve for the mapped pocket.",
                    action="reduce_depth",
                    matched_offender_index=idx,
                )
            )
        elif offender.rule_id == "R6":
            target_depth = float(offender.meta.get("depth_mm", 0.0))
            tool_diameter = float(offender.meta.get("tool_diameter_mm", 0.0))
            if candidate.feature_type == "extrude":
                target_depth = offender.target_value * tool_diameter
                proposals.append(
                    _proposal(
                        offender,
                        candidate,
                        new_value=target_depth,
                        rationale="Reduce pocket depth so the inferred tool can reach the feature safely.",
                        expected_effect="Rule 6 should improve for the mapped pocket.",
                        action="reduce_depth",
                        matched_offender_index=idx,
                    )
                )
            elif candidate.feature_type == "fillet":
                edge_radius = float(offender.meta.get("edge_radius_mm", 0.0))
                target_radius = max(edge_radius, tool_diameter * 0.65)
                proposals.append(
                    _proposal(
                        offender,
                        candidate,
                        new_value=target_radius,
                        rationale="Increase the governing fillet radius to allow a larger cutter.",
                        expected_effect="Rule 6 should improve by increasing the inferred tool diameter.",
                        action="increase_radius",
                        matched_offender_index=idx,
                    )
                )

    proposals.sort(key=lambda row: row.confidence, reverse=True)
    seen = set()
    unique: List[RemediationProposal] = []
    for proposal in proposals:
        key = (proposal.rule_id, proposal.feature_id, proposal.parameter_id, proposal.after)
        if key in seen:
            continue
        seen.add(key)
        unique.append(proposal)
    return unique
