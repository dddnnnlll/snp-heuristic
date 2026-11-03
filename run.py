"""Чтение независимых CSV-кейсов и вывод плана или ошибки каждого кейса."""

import argparse
import csv
from collections import defaultdict
from pathlib import Path

from allocator import Request, allocate


SUPPLY_FIELDS = ("case_id", "period", "item", "source_location", "available_qty")
REQUEST_FIELDS = ("case_id", "request_id", "dest_location", "priority",
                  "demand_qty", "min_lot", "rounding_value")


def read_csv(path: Path, required_fields: tuple[str, ...] = ()) -> list[dict[str, str]]:
    """Читает CSV и отклоняет повреждённую структуру, заголовки и пустые case_id."""
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source, strict=True)
        fields = reader.fieldnames
        if not fields or any(not name.strip() for name in fields):
            raise ValueError(f"{path.name}: отсутствует корректный заголовок CSV")
        if len(fields) != len(set(fields)):
            raise ValueError(f"{path.name}: повторные столбцы в заголовке")
        missing = sorted(set(required_fields) - set(fields))
        if missing:
            raise ValueError(f"{path.name}: отсутствуют столбцы {', '.join(missing)}")
        rows = []
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"{path.name}, строка {reader.line_num}: неверное число полей")
            if "case_id" in row and not row["case_id"].strip():
                raise ValueError(f"{path.name}, строка {reader.line_num}: пустой case_id")
            rows.append(row)
        return rows


def calculate(data_dir: Path) -> int:
    """Печатает результаты всех кейсов и возвращает ненулевой код при ошибках."""
    supplies = read_csv(data_dir / "supply.csv", SUPPLY_FIELDS)
    raw_requests = read_csv(data_dir / "requests.csv", REQUEST_FIELDS)
    grouped = defaultdict(list)
    for row in raw_requests:
        grouped[row["case_id"]].append(row)
    counts = defaultdict(int)
    supply_by_case = {}
    for row in supplies:
        counts[row["case_id"]] += 1
        supply_by_case[row["case_id"]] = row
    failures = 0
    for case_id in sorted(set(counts) | set(grouped)):
        try:
            if counts[case_id] != 1:
                raise ValueError("требуется ровно одна строка supply для кейса")
            supply = supply_by_case[case_id]
            requests = [Request(row["request_id"], int(row["priority"]),
                                int(row["demand_qty"]), int(row["min_lot"]),
                                int(row["rounding_value"])) for row in grouped[case_id]]
            available = int(supply["available_qty"])
            plan = allocate(available, requests)
        except (ValueError, KeyError) as error:
            print(f"{case_id}: ОШИБКА — {error}")
            failures += 1
            continue
        print(f"{case_id}: запас {available}; {supply['period']}, "
              f"{supply['item']}, {supply['source_location']}")
        for row in sorted(grouped[case_id], key=lambda row: row["request_id"]):
            print(f"  {row['request_id']} -> {row['dest_location']}: "
                  f"{plan[row['request_id']]} (спрос {row['demand_qty']})")
        print(f"  Остаток: {available - sum(plan.values())}")
    return int(failures > 0)


def main() -> int:
    """Принимает путь к CSV и запускает расчёт с понятной диагностикой ошибок чтения."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).parent / "data")
    args = parser.parse_args()
    try:
        return calculate(args.data_dir)
    except (OSError, UnicodeError, ValueError, KeyError, csv.Error) as error:
        print(f"Ошибка чтения данных: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
