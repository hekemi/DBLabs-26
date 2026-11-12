import random
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).with_name("phone.db")
COUNT = 60

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS fam (id INTEGER PRIMARY KEY AUTOINCREMENT, fam TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS name_ (id INTEGER PRIMARY KEY AUTOINCREMENT, name_ TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS otc (id INTEGER PRIMARY KEY AUTOINCREMENT, otc TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS street (id INTEGER PRIMARY KEY AUTOINCREMENT, street TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS main (
    uniq_id INTEGER PRIMARY KEY AUTOINCREMENT,
    fam INTEGER NOT NULL REFERENCES fam(id),
    name_ INTEGER NOT NULL REFERENCES name_(id),
    otc INTEGER REFERENCES otc(id),
    street INTEGER REFERENCES street(id),
    build TEXT,
    build_k TEXT,
    appr INTEGER,
    telephone TEXT NOT NULL UNIQUE
);
"""

# (мужская форма, женская форма)
SURNAMES = [
    ("Иванов", "Иванова"), ("Петров", "Петрова"), ("Сидоров", "Сидорова"),
    ("Смирнов", "Смирнова"), ("Кузнецов", "Кузнецова"), ("Попов", "Попова"),
    ("Васильев", "Васильева"), ("Соколов", "Соколова"), ("Михайлов", "Михайлова"),
    ("Новиков", "Новикова"), ("Фёдоров", "Фёдорова"), ("Морозов", "Морозова"),
    ("Волков", "Волкова"), ("Алексеев", "Алексеева"), ("Лебедев", "Лебедева"),
    ("Семёнов", "Семёнова"), ("Егоров", "Егорова"), ("Павлов", "Павлова"),
    ("Козлов", "Козлова"), ("Степанов", "Степанова"), ("Николаев", "Николаева"),
    ("Орлов", "Орлова"), ("Андреев", "Андреева"), ("Макаров", "Макарова"),
    ("Захаров", "Захарова"), ("Зайцев", "Зайцева"), ("Борисов", "Борисова"),
    ("Крылов", "Крылова"), ("Громов", "Громова"), ("Тихонов", "Тихонова"),
]
MALE_NAMES = ["Александр", "Дмитрий", "Максим", "Сергей", "Андрей", "Алексей",
              "Артём", "Илья", "Кирилл", "Михаил", "Никита", "Матвей", "Роман", "Егор"]
FEMALE_NAMES = ["Анна", "Мария", "Елена", "Ольга", "Татьяна", "Наталья",
                "Екатерина", "Юлия", "Ирина", "Светлана", "Дарья", "Полина", "Алиса", "Ксения"]
MALE_PATR = ["Александрович", "Дмитриевич", "Сергеевич", "Андреевич", "Алексеевич",
             "Иванович", "Михайлович", "Николаевич", "Владимирович", "Павлович"]
FEMALE_PATR = ["Александровна", "Дмитриевна", "Сергеевна", "Андреевна", "Алексеевна",
               "Ивановна", "Михайловна", "Николаевна", "Владимировна", "Павловна"]
STREETS = ["Ленина", "Мира", "Советская", "Гагарина", "Пушкина", "Лермонтова",
           "Парковая", "Молодёжная", "Центральная", "Школьная", "Победы",
           "Кирова", "Садовая", "Лесная", "Набережная"]


def ref_id(cur, table, value):
    cur.execute(f'INSERT OR IGNORE INTO "{table}" ("{table}") VALUES (?)', (value,))
    return cur.execute(f'SELECT id FROM "{table}" WHERE "{table}" = ?', (value,)).fetchone()[0]


def random_phone(used):
    while True:
        phone = "+7-{}-{:03d}-{:02d}-{:02d}".format(
            random.choice([900, 903, 905, 909, 915, 916, 925, 926, 977, 985, 999]),
            random.randint(0, 999), random.randint(0, 99), random.randint(0, 99),
        )
        if phone not in used:
            used.add(phone)
            return phone


def main():
    random.seed()
    con = sqlite3.connect(DB_PATH)
    con.executescript(SCHEMA)
    con.execute("PRAGMA foreign_keys = ON")
    cur = con.cursor()
    used = {r[0] for r in cur.execute("SELECT telephone FROM main")}

    for _ in range(COUNT):
        female = random.random() < 0.5
        surname = random.choice(SURNAMES)[1 if female else 0]
        name = random.choice(FEMALE_NAMES if female else MALE_NAMES)
        patr = random.choice(FEMALE_PATR if female else MALE_PATR) if random.random() < 0.85 else None
        street = random.choice(STREETS) if random.random() < 0.9 else None

        has_addr = street is not None
        build = str(random.randint(1, 120)) if has_addr and random.random() < 0.95 else None
        build_k = str(random.randint(1, 5)) if build and random.random() < 0.25 else None
        appr = random.randint(1, 250) if build and random.random() < 0.8 else None

        cur.execute(
            "INSERT INTO main (fam, name_, otc, street, build, build_k, appr, telephone) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                ref_id(cur, "fam", surname),
                ref_id(cur, "name_", name),
                ref_id(cur, "otc", patr) if patr else None,
                ref_id(cur, "street", street) if street else None,
                build, build_k, appr, random_phone(used),
            ),
        )

    con.commit()
    total = cur.execute("SELECT COUNT(*) FROM main").fetchone()[0]
    con.close()
    print(f"Готово. Записей в main: {total}")


if __name__ == "__main__":
    main()