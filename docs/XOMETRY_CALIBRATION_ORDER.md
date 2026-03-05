# Xometry Calibration Order

1. Quantity curve
- Tune: `qty_learning_rate`, `qty_factor_floor`
- Lock before moving on.

2. Material baseline
- Tune: material MRR relatives and `material_billet_cost_eur_per_kg`
- Lock before moving on.

3. Machine rates
- Tune: `machine_hourly_rate_3_axis_eur`, `machine_hourly_rate_5_axis_eur`
- Lock before moving on.

4. Surface penalty
- Tune: `surface_penalty_slope`, `surface_penalty_max_multiplier`

5. Feature-count penalties
- Tune: `hole_count_penalty_per_feature`, `hole_count_penalty_max_multiplier`
- Tune: `radius_count_penalty_per_feature`, `radius_count_penalty_max_multiplier`

6. Rule penalties (R1-R6)
- Tune per-rule multipliers using single-variable test parts.

7. Final validation
- Run mixed real parts/materials/qty and check error.

## Locking Rule
- Only tune one block at a time.
- Do not tune the next block until current block is within target error.
- If you change blocks 1-3 later, revalidate blocks 4-6.
