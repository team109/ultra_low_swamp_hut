"""Weights for fixed-budget natural terrain and conditional terrain cohorts."""


def stratify_terrain_panel(pilot, conditional_cohorts, trial_budget):
    """Combine an independent pilot with fixed-count conditional cohorts.

    Rows name their accepting source predicates in ``source_membership``.
    Cohort insertion order assigns overlapping predicates to disjoint strata.
    Each complete source cohort remains in its own denominator, including rows
    assigned to earlier strata. Source sampling uses no placement outcomes.
    """
    if trial_budget <= 0 or any(not rows for rows in conditional_cohorts.values()):
        raise ValueError(
            "The pilot budget and conditional cohort sizes must be positive"
        )
    order = list(conditional_cohorts)
    counts = {
        name: sum(name in row["source_membership"] for row in pilot) for name in order
    }

    def first_source(row):
        return next((name for name in order if name in row["source_membership"]), None)

    panel = [
        dict(row, trial_weight=1 / trial_budget, stratum="residual")
        for row in pilot
        if first_source(row) is None
    ]
    for name, rows in conditional_cohorts.items():
        if any(name not in row["source_membership"] for row in rows):
            raise ValueError(
                "Conditional observations must satisfy their source predicate"
            )
        weight = counts[name] / (trial_budget * len(rows))
        panel.extend(
            dict(row, trial_weight=weight, stratum=name)
            for row in rows
            if first_source(row) == name
        )
    return panel, counts
