"""SkillRegistry — 扫描 definitions/ 目录加载所有 SKILL.md，全局单例"""

from pathlib import Path
from typing import Dict, List, Optional

from app.skills.loader import SkillLoadError, load_skill_from_file
from app.skills.models import Skill

# Skill 定义目录
_DEFINITIONS_DIR = Path(__file__).parent / "definitions"

# 兜底 Skill 名
GENERIC_SKILL_NAME = "generic_oncall"


class SkillRegistry:
    """加载和管理所有 Skill"""

    def __init__(self, skills: Dict[str, Skill]) -> None:
        self._skills = skills

    def all(self) -> List[Skill]:
        return list(self._skills.values())

    def names(self) -> List[str]:
        return list(self._skills.keys())

    def get(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)

    def get_or_generic(self, name: Optional[str]) -> Skill:
        """取指定 Skill，不存在时回退到 generic_oncall"""
        if name and name in self._skills:
            return self._skills[name]
        generic = self._skills.get(GENERIC_SKILL_NAME)
        if generic is None:
            raise RuntimeError(f"兜底 Skill {GENERIC_SKILL_NAME!r} 缺失")
        return generic

    def to_router_menu(self) -> str:
        """生成给 Router LLM 看的全部 Skill 菜单"""
        cards = [s.to_router_card() for s in self._skills.values()]
        return "\n\n".join(cards)


def _scan_definitions(root: Path) -> Dict[str, Skill]:
    """扫描 definitions/ 目录加载所有 SKILL.md"""
    skills: Dict[str, Skill] = {}
    if not root.exists():
        print(f"[Skill] 定义目录不存在: {root}")
        return skills

    for skill_md in sorted(root.glob("*/SKILL.md")):
        try:
            skill = load_skill_from_file(skill_md)
        except SkillLoadError as e:
            print(f"[Skill] 跳过 {skill_md}: {e}")
            continue

        if skill.name in skills:
            print(f"[Skill] 重名 {skill.name!r}，后者覆盖前者: {skill_md}")
        skills[skill.name] = skill

    return skills


# 全局单例（启动时加载一次）
_registry: Optional[SkillRegistry] = None


def get_skill_registry() -> SkillRegistry:
    """获取全局 SkillRegistry 单例"""
    global _registry
    if _registry is None:
        skills = _scan_definitions(_DEFINITIONS_DIR)
        print(f"[Skill] 已加载 {len(skills)} 个 Skill: {list(skills.keys())}")
        _registry = SkillRegistry(skills)
    return _registry