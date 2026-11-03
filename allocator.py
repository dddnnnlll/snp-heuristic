"""Распределение одного запаса между заявками одного кейса."""

from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class Request:
    """Хранит потребность получателя и ограничения отгрузки."""

    request_id: str
    priority: int
    demand_qty: int
    min_lot: int
    rounding_value: int


def allocate(available_qty: int, requests: Iterable[Request]) -> dict[str, int]:
    """Распределяет запас по приоритетам и пропорциональным целям с учётом партий."""
    if type(available_qty) is not int or available_qty < 0:
        raise ValueError("available_qty должен быть целым неотрицательным числом")
    rows = list(requests)
    seen = set()
    errors = []
    for row in rows:
        if not isinstance(row.request_id, str) or not row.request_id.strip():
            errors.append("request_id должен быть непустой строкой")
            continue
        if row.request_id in seen:
            errors.append(f"{row.request_id}: повторный request_id")
        seen.add(row.request_id)
        for field, lower in (("priority", 1), ("demand_qty", 0),
                             ("min_lot", 0), ("rounding_value", 1)):
            value = getattr(row, field)
            if type(value) is not int or value < lower:
                errors.append(f"{row.request_id}: {field} должен быть целым >= {lower}")
    if errors:
        raise ValueError("; ".join(errors))

    rows.sort(key=lambda row: (row.priority, row.request_id))
    result = {row.request_id: 0 for row in rows}
    remaining = available_qty
    for priority in sorted({row.priority for row in rows}):
        group = [row for row in rows if row.priority == priority]
        limits = {}
        minimums = {}
        for row in group:
            step = row.rounding_value
            cap = row.demand_qty // step * step
            minimum = max(1, (row.min_lot + step - 1) // step) * step
            if minimum <= cap:
                limits[row.request_id] = cap
                minimums[row.request_id] = minimum
        group = [row for row in group if row.request_id in limits]
        if not group or remaining == 0:
            continue
        budget = min(remaining, sum(limits.values()))
        total_demand = sum(row.demand_qty for row in group)
        targets = {row.request_id: Fraction(budget * row.demand_qty, total_demand)
                   for row in group}
        for row in group:
            key = row.request_id
            qty = min(limits[key], int(targets[key]) // row.rounding_value
                      * row.rounding_value)
            if qty >= minimums[key]:
                result[key] = qty
                remaining -= qty
        while True:
            candidates = []
            for row in group:
                key = row.request_id
                increment = minimums[key] if result[key] == 0 else row.rounding_value
                if increment <= remaining and result[key] + increment <= limits[key]:
                    candidates.append((-(targets[key] - result[key]), key, increment))
            if not candidates:
                break
            _, key, increment = min(candidates)
            result[key] += increment
            remaining -= increment
    return result
