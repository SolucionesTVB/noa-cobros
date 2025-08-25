from db import init_schema, DB_PATH

if __name__ == "__main__":
    init_schema()
    print(f"✅ SQLite listo en: {DB_PATH}")
