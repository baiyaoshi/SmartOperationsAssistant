"""SKILL.md 解析器 — YAML frontmatter + Markdown body"""
"""读取skill.md转成skill对象"""
"""
SKILL.md 文件内容
    │
    ▼
---                          ← 文件以 --- 开头
name: host_resource...       ← 中间是 YAML 格式的元信息
display_name: 主机资源诊断
triggers: [cpu 高, 内存高]
---
                             ← 第二个 --- 之后是正文
# 主机资源诊断 Playbook      ← Markdown 格式的步骤模板
1. 检查 CPU 使用率...
    │
    │  loader.py 解析
    ▼
Skill 对象：
  name = "host_resource_diagnosis"
  display_name = "主机资源诊断"
  triggers = ["cpu 高", "内存高"]
  playbook = "# 主机资源诊断 Playbook1. 检查 CPU...
  """


import re
from pathlib import Path
from typing import Any, Dict, Tuple

import yaml

from app.skills.models import Skill


class SkillLoadError(Exception):
    """SKILL.md 解析失败"""


# 匹配: ---\n<yaml>\n---\n<body>
_FRONTMATTER_RE = re.compile(
    r"^---\s*\n(.*?)\n---\s*\n(.*)$",
    re.DOTALL,
)


def _split_frontmatter(text: str) -> Tuple[Dict[str, Any], str]:
    """把 SKILL.md 文本拆成 (frontmatter dict, body str)"""
    cleaned = text.lstrip("\ufeff")  # 去掉 Windows BOM
    match = _FRONTMATTER_RE.match(cleaned)
    if not match:
        raise SkillLoadError("SKILL.md 必须以 --- 开头，包含 YAML frontmatter")
    fm_text, body = match.group(1), match.group(2)
    try:
        fm = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError as e:
        raise SkillLoadError(f"YAML 语法错误: {e}") from e
    if not isinstance(fm, dict):
        raise SkillLoadError(f"frontmatter 必须是字典，实际是 {type(fm).__name__}")
    return fm, body.strip()


def load_skill_from_file(path: Path) -> Skill:
    """从 SKILL.md 文件加载单个 Skill"""
    text = path.read_text(encoding="utf-8")
    fm, body = _split_frontmatter(text)

    try:
        skill = Skill(
            **fm,
            playbook=body,
            source_path=str(path),
        )
    except Exception as e:
        raise SkillLoadError(f"Skill 字段校验失败 ({path}): {e}") from e

    print(f"  [Skill] 已加载: {skill.name} <- {path}")
    return skill