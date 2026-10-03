"""Small stdlib-only statistics helpers shared by the task generator and the labeller."""

import math
from statistics import fmean, variance


def _betacf(a: float, b: float, x: float) -> float:
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > 1e-300 else 1e-300)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1.0 + aa / c
        c = c if abs(c) > 1e-300 else 1e-300
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1.0 + aa / c
        c = c if abs(c) > 1e-300 else 1e-300
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-12:
            break
    return h


def betainc(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    ln_front = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    if x < (a + 1.0) / (a + b + 2.0):
        return math.exp(ln_front) * _betacf(a, b, x) / a
    return 1.0 - math.exp(ln_front) * _betacf(b, a, 1.0 - x) / b


def t_two_sided_p(t: float, df: float) -> float:
    return betainc(df / 2.0, 0.5, df / (df + t * t))


def welch_t_test(a: list[float], b: list[float]) -> tuple[float, float]:
    """Two-sided Welch's t-test of mean(a) vs mean(b). Returns (t, p)."""
    va, vb = variance(a) / len(a), variance(b) / len(b)
    t = (fmean(a) - fmean(b)) / math.sqrt(va + vb)
    df = (va + vb) ** 2 / (va**2 / (len(a) - 1) + vb**2 / (len(b) - 1))
    return t, t_two_sided_p(t, df)


def student_t_test(a: list[float], b: list[float]) -> tuple[float, float]:
    """Two-sided pooled-variance Student's t-test. Returns (t, p)."""
    na, nb = len(a), len(b)
    sp2 = ((na - 1) * variance(a) + (nb - 1) * variance(b)) / (na + nb - 2)
    t = (fmean(a) - fmean(b)) / math.sqrt(sp2 * (1 / na + 1 / nb))
    return t, t_two_sided_p(t, na + nb - 2)


def linregress(x: list[float], y: list[float]) -> tuple[float, float, float]:
    """Ordinary least squares y = intercept + slope * x. Returns (slope, intercept, r_squared)."""
    mx, my = fmean(x), fmean(y)
    sxx = sum((xi - mx) ** 2 for xi in x)
    sxy = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    syy = sum((yi - my) ** 2 for yi in y)
    slope = sxy / sxx
    return slope, my - slope * mx, sxy * sxy / (sxx * syy)


def classification_scores(y_true: list[int], y_pred: list[int]) -> dict[str, float]:
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    tn = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 0)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)
    sensitivity = tp / (tp + fn)
    specificity = tn / (tn + fp)
    return {
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "accuracy": (tp + tn) / len(y_true),
        "sensitivity": sensitivity,
        "specificity": specificity,
        "balanced_accuracy": (sensitivity + specificity) / 2,
    }


def parse_csv(text: str) -> list[dict[str, str]]:
    lines = [line for line in text.strip().splitlines() if line and not line.startswith("#")]
    header = lines[0].split(",")
    return [dict(zip(header, line.split(","))) for line in lines[1:]]


def mann_whitney_p(a: list[float], b: list[float]) -> float:
    """Two-sided Mann-Whitney U p-value (normal approximation with tie correction)."""
    pooled = sorted((v, i) for i, v in enumerate(a + b))
    ranks = [0.0] * len(pooled)
    tie_term, i = 0.0, 0
    while i < len(pooled):
        j = i
        while j + 1 < len(pooled) and pooled[j + 1][0] == pooled[i][0]:
            j += 1
        for k in range(i, j + 1):
            ranks[pooled[k][1]] = (i + j) / 2 + 1
        tie_term += (j - i + 1) ** 3 - (j - i + 1)
        i = j + 1
    na, nb = len(a), len(b)
    u = sum(ranks[:na]) - na * (na + 1) / 2
    n = na + nb
    sigma = math.sqrt(na * nb / 12 * ((n + 1) - tie_term / (n * (n - 1))))
    z = abs(u - na * nb / 2) / sigma
    return math.erfc(z / math.sqrt(2))


def pearson(x: list[float], y: list[float]) -> tuple[float, float]:
    """Pearson correlation and its two-sided p-value (t-test with n - 2 df)."""
    mx, my = fmean(x), fmean(y)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    r = sxy / math.sqrt(sum((a - mx) ** 2 for a in x) * sum((b - my) ** 2 for b in y))
    df = len(x) - 2
    return r, t_two_sided_p(r * math.sqrt(df / (1 - r * r)), df)


def cohens_d(a: list[float], b: list[float]) -> float:
    """(mean(a) - mean(b)) / pooled SD."""
    na, nb = len(a), len(b)
    sp = math.sqrt(((na - 1) * variance(a) + (nb - 1) * variance(b)) / (na + nb - 2))
    return (fmean(a) - fmean(b)) / sp
