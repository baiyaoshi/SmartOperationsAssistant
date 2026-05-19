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
