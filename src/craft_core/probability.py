"""Three-class outcome distributions, empirical priors and Brier scoring."""
import math


def distribution(beneficial, neutral):
    if any(type(v) not in (float, int) or not math.isfinite(v) or not 0 <= v <= 1
           for v in (beneficial, neutral)) or beneficial+neutral > 1+1e-9:
        raise ValueError('Invalid three-way prediction')
    return dict(Beneficial=beneficial, Neutral=neutral, Harmful=max(0., 1-beneficial-neutral))


def calibrated_distribution(raw, target):
    # Retain the model's conditional neutral/harmful split after the existing
    # primary-event correction. A certain raw improvement supplies no such split.
    rest = raw['Neutral']+raw['Harmful']
    fraction = raw['Neutral']/rest if rest else .5
    return distribution(target, (1-target)*fraction)


def prefix_distribution(records):
    counts = dict(Beneficial=1, Neutral=1, Harmful=1)  # Dirichlet(1,1,1)
    for r in records:
        if r.get('response') in counts:
            counts[r['response']] += 1
    n = sum(counts.values())
    return {k: v/n for k, v in counts.items()}


def score(probabilities, outcome):
    """Proper three-class score; abstention is reported, never called an error."""
    if outcome not in probabilities:
        return {'status': 'Inconclusive'}
    best = max(probabilities, key=probabilities.get)
    confident = probabilities[best] >= .6
    return {'status': 'Scored', 'outcome': outcome,
            'brier_multiclass': sum((p-int(k == outcome))**2 for k, p in probabilities.items()),
            'classification': best if confident else 'Abstain',
            'top_confidence': probabilities[best], 'top_correct': best == outcome,
            'correct': best == outcome if confident else None,
            'coverage_event': confident, 'threshold': .6}
