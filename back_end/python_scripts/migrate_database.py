# back_end/python_scripts/migrate_database.py
import os
import sqlite3
from library import *

def migrate():
    # 1. 读取配置文件定位数据库
    # 这里我们简单粗暴地手动读一下 config，或者你直接填绝对路径也行
    try:
        config_path = "../configs/magnus_config.yaml"
        config = load_from_yaml(config_path)
        root_path = config["server"]["root"]
        db_path = os.path.join(root_path, "database", "magnus.db")       
    except Exception as e:
        print(f"❌ 无法自动找到数据库路径: {e}")
        return

    print(f"📂 目标数据库: {db_path}")

    if not os.path.exists(db_path):
        print("❌ 数据库文件不存在！")
        return

    # 2. 连接数据库并修改表结构
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 核心 SQL：添加 result 列，允许为 NULL
        print("🛠️ 正在执行: ALTER TABLE jobs ADD COLUMN result TEXT;")
        cursor.execute("ALTER TABLE jobs ADD COLUMN result TEXT;")
        conn.commit()
        print("✅ 迁移成功！Result 列已添加。")
        
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("⚠️ 迁移跳过：Result 列已经存在了。")
        else:
            print(f"❌ 迁移失败: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()