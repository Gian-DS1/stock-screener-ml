"""El porcentaje global del pipeline debe ir de 0 a ~100 de forma monótona,
combinando la fase actual con su sub-progreso."""
from screener.pipeline import PHASE_PLANS, RunProgress


def _progress(kind: str) -> RunProgress:
    p = RunProgress.__new__(RunProgress)  # sin tocar la base de datos
    plan = PHASE_PLANS[kind]
    p.labels = [x[0] for x in plan]
    p.weights = [x[1] for x in plan]
    p.total_w = sum(p.weights)
    p.idx = 0
    p.last_overall = 0
    return p


def test_daily_avanza_monotono_por_fases():
    p = _progress("daily")
    prev = -1
    for label, _ in PHASE_PLANS["daily"]:
        v = p.overall_pct(label)
        assert 0 <= v <= 99
        assert v >= prev  # nunca retrocede
        prev = v
    # la última fase deja el global cerca del tope (el 100% lo pone el cierre)
    assert prev >= 80


def test_subprogreso_avanza_dentro_de_una_fase():
    p = _progress("backfill")
    # entrar a la fase pesada de 8-K
    base = p.overall_pct("Descargando 8-K (SEC)")
    mid = p.overall_pct("Descargando 8-K (SEC)", 5000, 10000)
    full = p.overall_pct("Descargando 8-K (SEC)", 10000, 10000)
    assert base < mid < full  # el sub-progreso mueve la barra dentro de la fase


def test_nunca_retrocede_aunque_baje_el_subprogreso():
    p = _progress("backfill")
    p.overall_pct("Descargando 8-K (SEC)", 9000, 10000)
    # una fase posterior que reporta frac 0 no debe bajar el global
    v = p.overall_pct("Analizando sentimiento (FinBERT)")
    assert v >= 0
    assert p.last_overall >= int(round(100 * (1 + 6 + 8 + 1) / sum(w for _, w in PHASE_PLANS["backfill"]) * 0))  # sanity
    # explícito: tras 90% del 8-K, el global no cae
    assert v >= 70


def test_score_simple_va_de_0_a_99():
    p = _progress("score")
    assert p.overall_pct("Generando señales") == 0
    assert p.overall_pct("Generando señales", 1, 1) == 99
