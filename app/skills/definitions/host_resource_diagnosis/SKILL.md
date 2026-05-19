---
name: host_resource_diagnosis
display_name: 主机资源诊断
description: CPU/内存/磁盘/本机卡顿等主机资源类故障
triggers:
  - 我的电脑
  - 我电脑
  - 本机卡顿
  - cpu 高
  - 内存高
  - 磁盘满
allowed_tools: []
risk_level: low
---

# 主机资源诊断 Playbook

## 适用场景
CPU 使用率高、内存占用高/OOM、磁盘满、系统卡顿等本机资源问题。

## 排查步骤
1. 检查 CPU 和内存使用率，确认是否存在资源占用过高的进程
2. 查看磁盘使用情况，排除磁盘满导致的卡顿
3. 汇总诊断结论，输出根因 + 处置建议
```

然后 `generic_oncall/SKILL.md`：

```markdown
---
name: generic_oncall
display_name: 通用 OnCall 兜底
description: 无法归类到具体故障类型时使用的通用排查思路
triggers:
  - 通用
  - 其他
  - 不确定
allowed_tools: []
risk_level: low
---

# 通用 OnCall 兜底 Playbook

## 适用场景
用户描述模糊，无法明确归类到 host_resource 或 network 等具体故障类型。

## 排查步骤
1. 确认用户问题的具体现象和影响范围
2. 根据已有信息给出初步判断
3. 提供下一步排查建议