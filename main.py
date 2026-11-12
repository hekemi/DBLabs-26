from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st


DB_PATH = Path(__file__).with_name("phone.db")
REFERENCE_TABLES = {
    "fam": {"title": "Фамилии", "column": "fam"},
    "name_": {"title": "Имена", "column": "name_"},
    "otc": {"title": "Отчества", "column": "otc"},
    "street": {"title": "Улицы", "column": "street"},
}

def reset_filters() -> None:
    st.session_state["filter_search"] = ""
    st.session_state["filter_family"] = []
    st.session_state["filter_street"] = []


def format_phone(value: str) -> str:
    digits = "".join(character for character in value if character.isdigit())
    if len(digits) == 11:
        country_code = "7" if digits[0] == "8" else digits[0]
        return (
            f"+{country_code}-{digits[1:4]}-{digits[4:7]}-"
            f"{digits[7:9]}-{digits[9:11]}"
        )
    return value


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def reference_options(table: str) -> dict[int, str]:
    column = REFERENCE_TABLES[table]["column"]
    with get_connection() as connection:
        rows = connection.execute(
            f'SELECT id, "{column}" FROM "{table}" ORDER BY "{column}"'
        ).fetchall()
    return {row[0]: row[1] for row in rows}


def load_main_records() -> pd.DataFrame:
    query = """
        SELECT
            m.uniq_id AS "ID",
            f.fam AS "Фамилия",
            n.name_ AS "Имя",
            o.otc AS "Отчество",
            s.street AS "Улица",
            m.build AS "Дом",
            m.build_k AS "Корпус",
            m.appr AS "Квартира",
            m.telephone AS "Телефон"
        FROM main AS m
        JOIN fam AS f ON f.id = m.fam
        JOIN name_ AS n ON n.id = m.name_
        LEFT JOIN otc AS o ON o.id = m.otc
        LEFT JOIN street AS s ON s.id = m.street
        ORDER BY m.uniq_id
    """
    with get_connection() as connection:
        return pd.read_sql_query(query, connection)


def execute_main_record(
    record_id: int | None,
    values: dict[str, Any],
) -> None:
    fields = ("fam", "name_", "otc", "street", "build", "build_k", "appr", "telephone")
    parameters = tuple(values[field] for field in fields)
    with get_connection() as connection:
        if record_id is None:
            connection.execute(
                """
                INSERT INTO main
                    (fam, name_, otc, street, build, build_k, appr, telephone)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                parameters,
            )
        else:
            connection.execute(
                """
                UPDATE main
                SET fam = ?, name_ = ?, otc = ?, street = ?, build = ?,
                    build_k = ?, appr = ?, telephone = ?
                WHERE uniq_id = ?
                """,
                parameters + (record_id,),
            )
        connection.commit()


def save_record_with_references(
    record_id: int | None,
    values: dict[str, Any],
    reference_values: dict[str, str | None],
) -> None:
    reference_ids: dict[str, int | None] = {}
    with get_connection() as connection:
        for table, value in reference_values.items():
            if value is None:
                reference_ids[table] = None
                continue
            column = REFERENCE_TABLES[table]["column"]
            connection.execute(
                f'INSERT OR IGNORE INTO "{table}" ("{column}") VALUES (?)',
                (value,),
            )
            row = connection.execute(
                f'SELECT id FROM "{table}" WHERE "{column}" = ?',
                (value,),
            ).fetchone()
            if row is None:
                raise sqlite3.Error(f"Не удалось сохранить значение: {value}")
            reference_ids[table] = int(row[0])

        record_values = {**values, **reference_ids}
        fields = (
            "fam", "name_", "otc", "street",
            "build", "build_k", "appr", "telephone",
        )
        parameters = tuple(record_values[field] for field in fields)
        if record_id is None:
            connection.execute(
                """
                INSERT INTO main
                    (fam, name_, otc, street, build, build_k, appr, telephone)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                parameters,
            )
        else:
            connection.execute(
                """
                UPDATE main
                SET fam = ?, name_ = ?, otc = ?, street = ?, build = ?,
                    build_k = ?, appr = ?, telephone = ?
                WHERE uniq_id = ?
                """,
                parameters + (record_id,),
            )
        connection.commit()


def delete_main_record(record_id: int) -> None:
    with get_connection() as connection:
        connection.execute("DELETE FROM main WHERE uniq_id = ?", (record_id,))
        connection.commit()


def save_reference_value(table: str, value: str) -> None:
    column = REFERENCE_TABLES[table]["column"]
    with get_connection() as connection:
        connection.execute(
            f'INSERT INTO "{table}" ("{column}") VALUES (?)',
            (value,),
        )
        connection.commit()


def get_or_create_reference_value(table: str, value: str) -> int:
    column = REFERENCE_TABLES[table]["column"]
    with get_connection() as connection:
        connection.execute(
            f'INSERT OR IGNORE INTO "{table}" ("{column}") VALUES (?)',
            (value,),
        )
        row = connection.execute(
            f'SELECT id FROM "{table}" WHERE "{column}" = ?',
            (value,),
        ).fetchone()
        if row is None:
            raise sqlite3.Error("Не удалось сохранить значение справочника.")
        connection.commit()
    return int(row[0])


def delete_reference_value(table: str, value_id: int) -> None:
    with get_connection() as connection:
        connection.execute(f'DELETE FROM "{table}" WHERE id = ?', (value_id,))
        connection.commit()


def show_error(error: Exception) -> None:
    if isinstance(error, sqlite3.IntegrityError):
        message = str(error)
        if "UNIQUE constraint failed" in message:
            st.error("Такая запись уже существует. Проверьте телефон или значение справочника.")
        elif "FOREIGN KEY constraint failed" in message:
            st.error("Нельзя удалить значение, которое используется в телефонном справочнике.")
        else:
            st.error(f"Операция отклонена базой данных: {message}")
    else:
        st.error(f"Не удалось выполнить операцию: {error}")


def render_record_form(
    record: pd.Series | None = None,
    form_key: str = "record_form",
) -> None:
    current_family = record["Фамилия"] if record is not None else None
    current_name = record["Имя"] if record is not None else None
    current_patronymic = record["Отчество"] if record is not None else None
    current_street = record["Улица"] if record is not None else None

    def reference_input(
        label: str,
        current_value: str | None,
        key: str,
    ) -> str:
        return st.text_input(
            label,
            value=current_value or "",
            placeholder="Введите своё значение",
            key=f"{form_key}_{key}",
        )

    with st.form(form_key):
        first, second = st.columns(2)
        with first:
            family = reference_input(
                "Фамилия *", current_family, "family"
            )
            name = reference_input(
                "Имя *", current_name, "name"
            )
            patronymic = reference_input(
                "Отчество", current_patronymic, "patronymic"
            )
            telephone = st.text_input(
                "Телефон *",
                value=str(record["Телефон"]) if record is not None else "",
                placeholder="+7-900-000-00-00",
            )
        with second:
            street = reference_input(
                "Улица", current_street, "street"
            )
            build = st.text_input(
                "Дом",
                value=str(record["Дом"]) if record is not None and pd.notna(record["Дом"]) else "",
            )
            build_k = st.text_input(
                "Корпус",
                value=str(record["Корпус"]) if record is not None and pd.notna(record["Корпус"]) else "",
            )
            apartment = st.number_input(
                "Квартира",
                min_value=0,
                step=1,
                value=int(record["Квартира"]) if record is not None and pd.notna(record["Квартира"]) else 0,
            )

        submitted = st.form_submit_button("Сохранить", type="primary")

    if submitted:
        if not telephone.strip():
            st.error("Телефон обязателен.")
            return
        input_values = (
            ("fam", family, False, "Фамилия"),
            ("name_", name, False, "Имя"),
            ("otc", patronymic, True, "Отчество"),
            ("street", street, True, "Улица"),
        )
        reference_values: dict[str, str | None] = {}
        for table, input_value, allow_empty, label in input_values:
            value = input_value.strip()
            if not value and not allow_empty:
                st.error(f"Введите значение: {label}.")
                return
            reference_values[table] = value or None
        values = {
            "build": build.strip() or None,
            "build_k": build_k.strip() or None,
            "appr": apartment or None,
            "telephone": format_phone(telephone.strip()),
        }
        try:
            save_record_with_references(
                int(record["ID"]) if record is not None else None,
                values,
                reference_values,
            )
            st.success("Запись сохранена.")
            st.rerun()
        except (sqlite3.IntegrityError, sqlite3.Error) as error:
            show_error(error)


def render_main_page() -> None:
    st.title("Телефонный справочник")
    st.caption(f"База данных: {DB_PATH.name}")
    records = load_main_records()

    with st.expander("Фильтры", expanded=True):
        first, second, third = st.columns(3)
        with first:
            search = st.text_input(
               "Поиск по ФИО, адресу или телефону",                
               key="filter_search",
            )
        with second:
            family_filter = st.multiselect(
                "Фамилия",
                sorted(records["Фамилия"].unique()),
                key="filter_family",
            )
        with third:
            street_filter = st.multiselect(
                "Улица",
                sorted(records["Улица"].dropna().unique()),
                key="filter_street",
            )
        st.button("Сбросить фильтры", on_click=reset_filters)

    filtered = records
    if search:
        mask = filtered.astype(str).apply(
            lambda column: column.str.contains(
                search,
                case=False,
                na=False,
                regex=False,
            )
        ).any(axis=1)
        filtered = filtered[mask]
    if family_filter:
        filtered = filtered[filtered["Фамилия"].isin(family_filter)]
    if street_filter:
        filtered = filtered[filtered["Улица"].isin(street_filter)]

    st.write(f"Найдено записей: **{len(filtered)}**")
    table_event = st.dataframe(
        filtered,
        width="stretch",
        hide_index=True,
        key="main_table",
        on_select="rerun",
        selection_mode="single-row",
    )
    selected_rows = table_event.selection.rows
    selected_record = (
        filtered.iloc[selected_rows[0]]
        if selected_rows and not filtered.empty
        else None
    )
    if selected_record is not None:
        st.subheader("Редактирование выбранной записи")
        st.caption("Изменения применятся после нажатия кнопки «Сохранить».")
        render_record_form(selected_record, form_key="selected_record")

    add_tab, delete_tab = st.tabs(["Добавить", "Удалить"])
    with add_tab:
        render_record_form(form_key="add_record")
    with delete_tab:
        if records.empty:
            st.info("Нет записей для удаления.")
        else:
            selected = st.selectbox(
                "Запись для удаления",
                records["ID"].tolist(),
                format_func=lambda record_id: (
                    f"#{record_id}: "
                    f"{records.loc[records['ID'] == record_id, 'Фамилия'].iloc[0]} "
                    f"{records.loc[records['ID'] == record_id, 'Телефон'].iloc[0]}"
                ),
                key="delete_record_id",
            )
            if st.button("Удалить запись", type="secondary"):
                if isinstance(selected, int):
                    try:
                        delete_main_record(selected)
                        st.success("Запись удалена.")
                        st.rerun()
                    except sqlite3.Error as error:
                        show_error(error)


def render_reference_page() -> None:
    st.title("Справочники")
    st.caption("Здесь можно просматривать и редактировать значения, используемые в основной таблице.")
    for table, metadata in REFERENCE_TABLES.items():
        with st.expander(metadata["title"], expanded=True):
            options = reference_options(table)
            table_data = pd.DataFrame(
                [{"ID": value_id, metadata["title"]: value} for value_id, value in options.items()]
            )
            st.dataframe(table_data, width="stretch", hide_index=True)
            add_col, delete_col = st.columns(2)
            with add_col:
                with st.form(f"add_{table}"):
                    new_value = st.text_input(f"Добавить значение ({metadata['title'].lower()})")
                    if st.form_submit_button("Добавить"):
                        if not new_value.strip():
                            st.error("Значение не может быть пустым.")
                        else:
                            try:
                                save_reference_value(table, new_value.strip())
                                st.success("Значение добавлено.")
                                st.rerun()
                            except sqlite3.Error as error:
                                show_error(error)
            with delete_col:
                if options:
                    value_id = st.selectbox(
                        "Удалить значение",
                        list(options),
                        format_func=lambda option: str(options[option]),
                        key=f"delete_{table}",
                    )
                    if st.button("Удалить", key=f"delete_button_{table}"):
                        if value_id is not None:
                            try:
                                delete_reference_value(table, value_id)
                                st.success("Значение удалено.")
                                st.rerun()
                            except sqlite3.Error as error:
                                show_error(error)


def main() -> None:
    st.set_page_config(page_title="Телефонный справочник", page_icon="☎️", layout="wide")
    if not DB_PATH.exists():
        st.error(f"Файл базы данных не найден: {DB_PATH}")
        st.stop()

    page = st.sidebar.radio("Раздел", ["Телефонный справочник", "Справочники"])
    if page == "Телефонный справочник":
        render_main_page()
    else:
        render_reference_page()


if __name__ == "__main__":
    main()