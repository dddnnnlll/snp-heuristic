"""Примеры из задания и самостоятельные проверки контракта распределения."""

import itertools
import random
from pathlib import Path

import pytest

from allocator import Request, allocate
from run import calculate, read_csv


DATA = Path(__file__).resolve().parents[1] / "data"
EXPECTED = {
    "CASE_01": ({"R-101": 25, "R-102": 25, "R-103": 25}, 25),
    "CASE_02": ({"R-201": 40, "R-202": 30, "R-203": 30, "R-204": 0}, 0),
    "CASE_04": ({"R-401": 20, "R-402": 20, "R-403": 19,
                 "R-404": 19, "R-405": 19}, 0),
    "CASE_05": ({"R-501": 25, "R-502": 30, "R-503": 5}, 440),
    "CASE_06": ({"R-601": 100, "R-602": 0, "R-603": 77}, 23),
    "CASE_07": ({"R-701": 100, "R-702": 0, "R-703": 0}, 0),
}


def load_case(case_id):
    """Извлекает запас и типизированные заявки выбранного исходного кейса."""
    supply = next(row for row in read_csv(DATA / "supply.csv") if row["case_id"] == case_id)
    requests = [Request(row["request_id"], int(row["priority"]), int(row["demand_qty"]),
                        int(row["min_lot"]), int(row["rounding_value"]))
                for row in read_csv(DATA / "requests.csv") if row["case_id"] == case_id]
    return int(supply["available_qty"]), requests


@pytest.mark.parametrize("case_id", EXPECTED)
def test_csv_plan(case_id):
    """Фиксирует выбранный план и остаток каждого корректного CSV-кейса, защищая правила от изменений."""
    supply, requests = load_case(case_id)
    expected, leftover = EXPECTED[case_id]
    actual = allocate(supply, requests)
    assert actual == expected
    assert supply - sum(actual.values()) == leftover


def test_invalid_csv_case():
    """Запрещает молча исправлять CASE_03, иначе отрицательный спрос и нулевая кратность будут скрыты."""
    supply, requests = load_case("CASE_03")
    with pytest.raises(ValueError) as error:
        allocate(supply, requests)
    assert "R-302: demand_qty" in str(error.value)
    assert "R-304: rounding_value" in str(error.value)


def test_proportional_shares():
    """Сохраняет соотношение 2:1 при равном приоритете, иначе большие заявки потеряют свою долю."""
    requests = [Request("A", 1, 100, 0, 1), Request("B", 1, 50, 0, 1)]
    assert allocate(90, requests) == {"A": 60, "B": 30}


def test_minimum_is_rounded_up():
    """Округляет минимум 30 до партии 50 при кратности 25, иначе возможна недопустимая отгрузка."""
    requests = [Request("A", 1, 100, 30, 25)]
    assert allocate(49, requests) == {"A": 0}
    assert allocate(50, requests) == {"A": 50}


def test_greedy_rule_is_not_global_utilization_optimum():
    """Фиксирует ограничение жадного выбора, иначе правило незаметно сменится на максимизацию отгрузки."""
    requests = [Request("A", 1, 10, 6, 6), Request("B", 1, 10, 10, 5)]
    assert allocate(10, requests) == {"A": 6, "B": 0}


def test_unusable_high_priority_stock_goes_lower():
    """Передаёт остаток младшему при невозможной старшей партии, иначе пригодный запас простаивает."""
    requests = [Request("A", 1, 100, 50, 25), Request("B", 2, 40, 0, 10)]
    assert allocate(40, requests) == {"A": 0, "B": 40}


def test_input_order_does_not_change_ties():
    """Разрешает ничьи по идентификатору независимо от порядка входа, иначе перестановка CSV меняет план."""
    requests = [Request(key, 1, 50, 0, 10) for key in ("C", "A", "B")]
    for permutation in itertools.permutations(requests):
        assert allocate(100, iter(permutation)) == {"A": 40, "B": 30, "C": 30}


@pytest.mark.parametrize("supply, requests", [
    (0, [Request("A", 1, 5, 0, 1)]),
    (10, []),
    (10, [Request("A", 1, 0, 0, 1)]),
])
def test_empty_or_zero(supply, requests):
    """Возвращает нулевые отгрузки для пустого спроса или запаса, иначе появятся фиктивные поставки."""
    assert allocate(supply, requests) == {row.request_id: 0 for row in requests}


@pytest.mark.parametrize("supply, requests", [
    (-1, []), (True, []),
    (10, [Request("A", 0, 10, 0, 1)]),
    (10, [Request("A", 1, 10, -1, 1)]),
    (10, [Request("A", 1, 10, 0, -1)]),
    (10, [Request("A", 1, 1.5, 0, 1)]),
    (10, [Request("", 1, 10, 0, 1)]),
    (10, [Request("A", 1, 10, 0, 1), Request("A", 2, 5, 0, 1)]),
])
def test_reject_invalid_input(supply, requests):
    """Отклоняет некорректные поля и повторные ID, иначе расчёт скрывает ошибки или теряет заявки."""
    with pytest.raises(ValueError):
        allocate(supply, requests)


def test_generated_invariants():
    """Проверяет ограничения на 300 воспроизводимых наборах, иначе частные примеры могут скрыть перерасход."""
    rng = random.Random(42)
    for _ in range(300):
        supply = rng.randrange(200)
        requests = [Request(str(index), rng.randint(1, 3), rng.randrange(100),
                            rng.randrange(60), rng.randint(1, 15))
                    for index in range(rng.randrange(8))]
        plan = allocate(supply, requests)
        assert sum(plan.values()) <= supply
        assert plan == allocate(supply, reversed(requests))
        leftover = supply - sum(plan.values())
        for row in requests:
            qty = plan[row.request_id]
            assert 0 <= qty <= row.demand_qty
            assert qty == 0 or (qty >= row.min_lot and qty % row.rounding_value == 0)
            next_lot = (row.rounding_value if qty else
                        max(1, (row.min_lot + row.rounding_value - 1)
                            // row.rounding_value) * row.rounding_value)
            assert next_lot > leftover or qty + next_lot > row.demand_qty


def test_cli_continues_after_invalid_case(capsys):
    """Продолжает расчёт после ошибки CASE_03 и сигнализирует о ней кодом 1, иначе теряются следующие кейсы."""
    assert calculate(DATA) == 1
    output = capsys.readouterr().out
    assert "CASE_03: ОШИБКА" in output
    assert "CASE_07: запас" in output


def test_duplicate_supply_is_rejected(tmp_path, capsys):
    """Отклоняет неоднозначный запас одного кейса, иначе одна строка может незаметно заменить другую."""
    (tmp_path / "supply.csv").write_text(
        "case_id,period,item,source_location,available_qty\n"
        "X,2026-01,A,P,10\nX,2026-01,A,P,20\n", encoding="utf-8")
    (tmp_path / "requests.csv").write_text(
        "case_id,request_id,dest_location,priority,demand_qty,min_lot,rounding_value\n",
        encoding="utf-8")
    assert calculate(tmp_path) == 1
    assert "ровно одна строка supply" in capsys.readouterr().out
