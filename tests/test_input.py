"""Проверки структуры CSV, связей между файлами и независимости кейсов."""

import sys

import pytest

from run import REQUEST_FIELDS, SUPPLY_FIELDS, calculate, main, read_csv


def write_data(directory, supplies, requests):
    """Создаёт пару временных CSV из строк данных с заданными заголовками."""
    (directory / "supply.csv").write_text(
        ",".join(SUPPLY_FIELDS) + "\n" + supplies, encoding="utf-8")
    (directory / "requests.csv").write_text(
        ",".join(REQUEST_FIELDS) + "\n" + requests, encoding="utf-8")


@pytest.mark.parametrize("content, message", [
    ("", "заголовок"),
    ("case_id,case_id\nA,A\n", "повторные столбцы"),
    ("case_id,\nA,1\n", "заголовок"),
    ("case_id,qty\nA\n", "число полей"),
    ("case_id,qty\nA,1,extra\n", "число полей"),
    ("case_id,qty\n,1\n", "пустой case_id"),
])
def test_csv_structure_is_validated(tmp_path, content, message):
    """Отклоняет повреждённую структуру CSV явно, иначе поля могут потеряться или вызвать traceback."""
    source = tmp_path / "input.csv"
    source.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        read_csv(source)


def test_missing_header_has_friendly_cli_error(tmp_path, monkeypatch, capsys):
    """Сообщает об отсутствующих столбцах кодом 1, иначе неполный файл может выглядеть пустым корректным."""
    (tmp_path / "supply.csv").write_text("case_id\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["run.py", "--data-dir", str(tmp_path)])
    assert main() == 1
    assert "отсутствуют столбцы" in capsys.readouterr().out


def test_case_without_requests_keeps_stock(tmp_path, capsys):
    """Сохраняет весь запас кейса без заявок, иначе отсутствие спроса может стать ошибкой расчёта."""
    write_data(tmp_path, "A,2026-01,X,P,10\n", "")
    assert calculate(tmp_path) == 0
    assert "Остаток: 10" in capsys.readouterr().out


def test_orphan_request_does_not_stop_other_cases(tmp_path, capsys):
    """Отклоняет заявку без supply отдельно от корректного кейса, иначе исчезают независимые результаты."""
    write_data(tmp_path, "B,2026-01,X,P,10\n",
               "A,R1,D,1,5,0,1\nB,R2,D,1,5,0,1\n")
    assert calculate(tmp_path) == 1
    output = capsys.readouterr().out
    assert "A: ОШИБКА" in output
    assert "R2 -> D: 5" in output


def test_bad_number_does_not_stop_other_cases(tmp_path, capsys):
    """Ограничивает ошибку числового поля одним кейсом, иначе неверный спрос блокирует остальные планы."""
    write_data(tmp_path, "A,2026-01,X,P,10\nB,2026-01,X,P,10\n",
               "A,R1,D,1,oops,0,1\nB,R2,D,1,5,0,1\n")
    assert calculate(tmp_path) == 1
    output = capsys.readouterr().out
    assert "A: ОШИБКА" in output
    assert "B: запас" in output


def test_missing_file_has_friendly_error(tmp_path, monkeypatch, capsys):
    """Возвращает понятную ошибку для отсутствующего файла, иначе запуск завершается необработанным исключением."""
    monkeypatch.setattr(sys, "argv", ["run.py", "--data-dir", str(tmp_path)])
    assert main() == 1
    assert "Ошибка чтения данных" in capsys.readouterr().out
