# back_end/python_scripts/migrate_database.py
import os
import sqlite3
import sys
from datetime import datetime

# 确保能导入 library
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from library import load_from_yaml

def migrate():
    # 1. 读取配置文件定位数据库
    try:
        # 假设脚本在 back_end/python_scripts/ 下运行
        config_path = "../configs/magnus_config.yaml"
        if not os.path.exists(config_path):
            # Fallback: 尝试绝对路径或其他位置
            config_path = "../../configs/magnus_config.yaml"
            
        config = load_from_yaml(config_path)
        root_path = config["server"]["root"]
        
        # 尝试两个常见的路径，确保能找到
        db_path_candidates = [
            os.path.join(root_path, "magnus.db"),            # 根目录
            os.path.join(root_path, "database", "magnus.db") # database 子目录
        ]
        
        db_path = None
        for p in db_path_candidates:
            if os.path.exists(p):
                db_path = p
                break
        
        if not db_path:
            # 如果文件不存在，默认使用第一个路径（可能还没创建）
            db_path = db_path_candidates[0]
            
    except Exception as e:
        print(f"❌ 无法自动找到数据库路径: {e}")
        return

    print(f"📂 目标数据库: {db_path}")

    if not os.path.exists(db_path):
        print("❌ 数据库文件不存在！请先运行 Server 生成数据库。")
        return

    # 2. 连接数据库并修改表结构
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # === 任务 1: Jobs 表新增 Result ===
    try:
        print("🛠️ [Jobs] 检查 result 列...")
        cursor.execute("ALTER TABLE jobs ADD COLUMN result TEXT;")
        print("✅ [Jobs] result 列已添加。")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("⚠️ [Jobs] result 列已存在，跳过。")
        else:
            print(f"❌ [Jobs] 迁移失败: {e}")

    # === 任务 2: Services 表新增 updated_at ===
    try:
        print("🛠️ [Services] 检查 updated_at 列...")
        cursor.execute("ALTER TABLE services ADD COLUMN updated_at TIMESTAMP;")
        print("✅ [Services] updated_at 列已添加。")
        
        # 数据回填 (Backfill)
        # 为旧数据赋予初始时间，防止前端排序炸裂
        now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        print(f"🧹 [Services] 正在为旧数据回填 updated_at = {now_str} ...")
        
        cursor.execute("UPDATE services SET updated_at = ? WHERE updated_at IS NULL", (now_str,))
        print(f"✅ [Services] 回填完成，影响行数: {cursor.rowcount}")

    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("⚠️ [Services] updated_at 列已存在，跳过。")
        else:
            print(f"❌ [Services] 迁移失败: {e}")

    # 提交并关闭
    conn.commit()
    conn.close()
    print("\n🎉 所有迁移任务执行完毕。")

if __name__ == "__main__":
    migrate()