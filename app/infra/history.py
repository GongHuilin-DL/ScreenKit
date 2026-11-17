"""历史记录管理：记录最近生成的截图和录屏。"""
import json
from datetime import datetime
from pathlib import Path

from app.infra.logger import get_logger
from app.infra.paths import CONFIG_DIR

logger = get_logger("infra.history")

HISTORY_FILE = CONFIG_DIR / "history.json"
MAX_RECORDS = 50


def load_history() -> list[dict]:
    """加载历史记录。"""
    if not HISTORY_FILE.is_file():
        return []
    try:
        with HISTORY_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        logger.warning("读取历史记录失败: %s", e)
        return []


def add_record(record_type: str, file_path: str) -> None:
    """添加一条历史记录。"""
    path = Path(file_path).resolve()
    if not path.is_file():
        return

    stat = path.stat()
    
    records = load_history()
    new_record = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": record_type,
        "path": str(path),
        "name": path.name,
        "size": stat.st_size,
        "mtime": stat.st_mtime,
    }
    
    records.insert(0, new_record)
    if len(records) > MAX_RECORDS:
        records = records[:MAX_RECORDS]

    try:
        with HISTORY_FILE.open("w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("保存历史记录失败: %s", e)


def remove_record(file_path: str) -> None:
    """从历史记录中移除特定路径。"""
    records = load_history()
    records = [r for r in records if r.get("path") != file_path]
    try:
        with HISTORY_FILE.open("w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("保存历史记录失败: %s", e)


def clear_missing_records() -> int:
    """清理所有文件已丢失或失效的记录，返回清理数量。"""
    records = load_history()
    valid_records = []
    removed_count = 0
    
    for r in records:
        path = Path(r.get("path", ""))
        is_valid = False
        if path.is_file():
            if "size" in r and path.stat().st_size != r["size"]:
                is_valid = False # 文件被同名文件冒充
            else:
                is_valid = True
                
        if is_valid:
            valid_records.append(r)
        else:
            removed_count += 1
            
    if removed_count > 0:
        try:
            with HISTORY_FILE.open("w", encoding="utf-8") as f:
                json.dump(valid_records, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("保存历史记录失败: %s", e)
            
    return removed_count


def delete_records(record_type: str | None = None, delete_files: bool = True) -> int:
    """删除指定类型的记录（可选同时删除磁盘文件），返回删除成功的数量。"""
    records = load_history()
    keep_records = []
    deleted_count = 0
    
    for rec in records:
        # 如果指定了类型，且不匹配，则保留
        if record_type and rec.get("type") != record_type:
            keep_records.append(rec)
            continue
            
        # 如果匹配（或没有指定类型代表全部），执行删除
        if delete_files:
            path = Path(rec.get("path", ""))
            if path.is_file():
                try:
                    path.unlink()
                except Exception as e:
                    logger.error("删除文件失败 %s: %s", path, e)
                    # 删不掉（比如被占用），则保留该记录
                    keep_records.append(rec)
                    continue
                    
        deleted_count += 1
        
    try:
        with HISTORY_FILE.open("w", encoding="utf-8") as f:
            json.dump(keep_records, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("保存历史记录失败: %s", e)
        
    return deleted_count