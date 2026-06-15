from __future__ import annotations

from typing import Any


def render_trend_report(title: str, ranking: list[dict[str, Any]], evidence: list[dict[str, str]]) -> str:
    lines = [
        f"# {title}",
        "",
        "## 结论",
        f"- 结论 1：最近半年 AI Agent 领域热度上升最快的机构是 {ranking[0]['name']}。",
        "- 结论 2：该判断由机构热度、论文热度和学者/新闻信号共同支持。",
        "",
        "## 排名",
        "| 排名 | 机构 | 半年热度 | 上一半年热度 | 增长量 | 增长率 |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for idx, row in enumerate(ranking, start=1):
        lines.append(
            f"| {idx} | {row['name']} | {row['current_hotness']} | {row['previous_hotness']} | "
            f"{row['absolute_growth']} | {row['growth_rate']:.2f} |"
        )
    lines.extend(["", "## 证据链"])
    for item in evidence:
        lines.extend([f"### {item['evidence_id']}: {item['title']}", item["summary"], ""])
    lines.extend(
        [
            "## 方法说明",
            "本报告基于 AI Index fixture 数据，模拟学者库、论文库、机构库及其关联字段。当前结果不代表真实 AI Index 线上数据。",
            "",
            "## 限制",
            "- 当前使用 mock fixture，不是线上 API。",
            "- 热度指标为模拟字段。",
            "- Verifier 当前只检查 claim-evidence coverage，不做真实事实裁判。",
        ]
    )
    return "\n".join(lines)
