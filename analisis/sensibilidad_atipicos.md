# Sensibilidad de la marca de atípico

Generado por `analisis/sensibilidad_atipicos.py` con el Excel de Crédito Público cuya última operación es del 17/11/2026 (168,021 operaciones; 61 instrumentos; 30 bonos vigentes en DOP y USD).

Una fila es atípica si su rendimiento está fuera de [mínimo, máximo]. Los bonos vigentes se comparan entre `rendimiento_actual()` con el método oficial y con `excluir_atipicos=True`. El umbral vigente en rdfin es 0 / 30.

| Mín. / máx. (%) | Filas marcadas | % de filas | Instrumentos con alguna fila marcada | Bonos vigentes cuyo rendimiento cambia | De ellos, desaparecen | Cambio máximo (pp) |
| --- | --- | --- | --- | --- | --- | --- |
| -5 / 20 | 636 | 0.38% | 20 | 0 | 0 | 0.0000 |
| -5 / 30 | 494 | 0.29% | 13 | 0 | 0 | 0.0000 |
| -5 / 50 | 388 | 0.23% | 13 | 0 | 0 | 0.0000 |
| 0 / 20 | 1,728 | 1.03% | 22 | 2 | 0 | 1.5332 |
| 0 / 30 | 1,586 | 0.94% | 15 | 2 | 0 | 1.5332 |
| 0 / 50 | 1,480 | 0.88% | 15 | 2 | 0 | 1.5332 |
| 1 / 20 | 3,441 | 2.05% | 39 | 2 | 0 | 6.0050 |
| 1 / 30 | 3,299 | 1.96% | 37 | 2 | 0 | 6.0050 |
| 1 / 50 | 3,193 | 1.90% | 37 | 2 | 0 | 6.0050 |
