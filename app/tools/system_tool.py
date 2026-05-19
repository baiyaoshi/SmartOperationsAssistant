"""系统诊断工具 — 基于 psutil 获取真实系统数据"""
import psutil

def get_cpu_usage() -> str:
    """获取 CPU 使用率"""
    percent = psutil.cpu_percent(interval=1)  #采样 1 秒
    core_count = psutil.cpu_count()
    return f"CPU 使用率: {percent}% ({core_count} 核)"


def get_memory_usage() -> str:
    """获取内存使用情况"""
    mem = psutil.virtual_memory()
    total_gb = mem.total / (1024 ** 3)
    used_gb = mem.used / (1024 ** 3)
    return f"内存: 已用 {used_gb:.1f}GB / 总共 {total_gb:.1f}GB ({mem.percent}%)"


def get_disk_usage(path: str = "C:\\") -> str:
    """获取磁盘使用情况

    Args:
        path: 磁盘路径，默认 C:\\
    """
    disk = psutil.disk_usage(path)
    total_gb = disk.total / (1024 ** 3)
    used_gb = disk.used / (1024 ** 3)
    return f"磁盘 {path}: 已用 {used_gb:.1f}GB / 总共 {total_gb:.1f}GB ({disk.percent}%)"


def get_top_processes(count: int = 5) -> str:
    """获取占用 CPU和内存 最高的前 N 个进程
    Args:
        count: 返回进程数，默认 5
    """
    processes = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            processes.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    # 按CPU 使用率排序
    cpu_sorted= sorted(processes,key=lambda p: p.get("cpu_percent", 0) or 0, reverse=True)
    # 按内存占用排序
    mem_sorted= sorted(processes,key=lambda p: p.get("memory_percent", 0) or 0, reverse=True)

    lines = [f"TOP {count} 进程 (按 CPU):"]
    for p in cpu_sorted[:count]:
        name = p["name"]
        cpu = p["cpu_percent"] or 0
        mem = p["memory_percent"] or 0
        lines.append(f"  {name} — CPU {cpu:.1f}%, 内存 {mem:.1f}%")

    lines.append("")
    lines.append(f"TOP {count} 进程 (按内存):")
    for p in mem_sorted[:count]:
        name = p["name"]
        cpu = p["cpu_percent"] or 0
        mem = p["memory_percent"] or 0
        lines.append(f"  PID {p['pid']} {name} — CPU {cpu:.1f}%, 内存 {mem:.1f}%")

    return "\n".join(lines)



cpu_tool_definition = {
    "type": "function",
    "function": {
        "name": "get_cpu_usage",
        "description": "获取系统 CPU 使用率",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
}

memory_tool_definition = {
    "type": "function",
    "function": {
        "name": "get_memory_usage",
        "description": "获取系统内存使用情况",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
}

disk_tool_definition = {
    "type": "function",
    "function": {
        "name": "get_disk_usage",
        "description": "获取指定磁盘的使用情况",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "磁盘路径，例如 C:\\ 或 D:\\"
                }
            },
            "required": []
        }
    }
}

top_processes_tool_definition = {
    "type": "function",
    "function": {
        "name": "get_top_processes",
        "description": "获取占用 CPU 最高的前 N 个进程列表以及获取占用 CPU 最高的前 N 个进程列表",
        "parameters": {
            "type": "object",
            "properties": {
                "count": {
                    "type": "integer",
                    "description": "返回的进程数量，默认 5"
                }
            },
            "required": []
        }
    }
}
