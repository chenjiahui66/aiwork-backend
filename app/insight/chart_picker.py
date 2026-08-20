"""
图表选择器 — 根据查询结果(列类型 + 行数)自动选 ECharts 配置

前端需要的格式:
{
  "chart_type": "bar" | "line" | "pie" | "scatter" | "table",
  "echarts_option": {...},     # ECharts 直接可用的 option
  "columns": [...],            # 列名
  "rows": [...]                # 数据行
}

策略(简化版):
- 1 列(只有 label) → 不画图,返回 table
- 2 列(分类+数值) → bar(<=8 行) 或 pie(<=6 行且 label 不重复)
- 3 列以上(类别 + 时间 + 数值) → line
- 行数太多 → 自动转 table
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)


def pick_chart(columns: list[str], rows: list[list[Any]]) -> dict:
    """
    选图表类型 + 生成 ECharts option

    columns: ["category", "value"] 或 ["date", "category", "value"]
    rows:    [["华东", 1234.5], ...]
    """
    n_cols = len(columns)
    n_rows = len(rows)

    # 列名小写化方便判断
    col_lower = [c.lower() for c in columns]

    # === 特殊情形 ===
    if n_cols == 0 or n_rows == 0:
        return {
            "chart_type": "table",
            "echarts_option": None,
            "columns": columns,
            "rows": rows,
            "message": "无数据",
        }

    if n_cols == 1:
        return {
            "chart_type": "table",
            "echarts_option": None,
            "columns": columns,
            "rows": rows,
            "message": "单列查询,显示为表格",
        }

    # === 2 列 ===
    if n_cols == 2:
        label_col, value_col = columns
        # 判断 value 列是不是数字
        is_numeric = all(
            isinstance(r[1], (int, float)) and not isinstance(r[1], bool)
            for r in rows if len(r) >= 2
        )

        if not is_numeric:
            return {
                "chart_type": "table",
                "echarts_option": None,
                "columns": columns,
                "rows": rows,
                "message": "两列但非数值,显示表格",
            }

        labels = [str(r[0]) for r in rows]
        values = [r[1] for r in rows]

        # 决定: 饼图(<=6 行 + label 唯一) vs 柱状图
        unique_labels = len(set(labels))
        if n_rows <= 6 and unique_labels == n_rows:
            return {
                "chart_type": "pie",
                "echarts_option": _pie_option(labels, values, value_col),
                "columns": columns,
                "rows": rows,
            }
        else:
            return {
                "chart_type": "bar",
                "echarts_option": _bar_option(labels, values, value_col),
                "columns": columns,
                "rows": rows,
            }

    # === 3 列, 假设 [时间, 类别, 数值] 或 [类别, 子类, 数值] ===
    # 简化: 如果第 1 列像时间(date/month) → 折线
    # 否则堆叠柱状
    first_col_is_date = any(
        kw in columns[0].lower()
        for kw in ["date", "month", "time", "日期", "时间", "年月"]
    )

    # 把第 1 列当 X 轴, 第 3 列当 Y 轴, 第 2 列当系列
    x_values = [str(r[0]) for r in rows]
    series_col = columns[2] if n_cols >= 3 else columns[1]
    series_vals = [r[2] if len(r) > 2 else 0 for r in rows]
    labels = [str(r[1]) if len(r) > 1 else "" for r in rows]

    if first_col_is_date:
        # 折线图 — 按 (x, series) 聚合
        return {
            "chart_type": "line",
            "echarts_option": _line_option(x_values, labels, series_vals, series_col),
            "columns": columns,
            "rows": rows,
        }
    else:
        # 堆叠柱状(简化: 单系列)
        return {
            "chart_type": "bar",
            "echarts_option": _bar_option(
                [f"{x}|{l}" for x, l in zip(x_values, labels)],
                series_vals,
                series_col,
            ),
            "columns": columns,
            "rows": rows,
        }


# ===== ECharts option 生成器 =====

def _bar_option(labels: list[str], values: list, name: str) -> dict:
    return {
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "grid": {"left": "3%", "right": "4%", "bottom": "8%", "containLabel": True},
        "xAxis": {
            "type": "category",
            "data": labels,
            "axisLabel": {"rotate": labels and len(max(labels, key=len)) > 6 and 30 or 0},
        },
        "yAxis": {"type": "value"},
        "series": [{
            "name": name,
            "type": "bar",
            "data": values,
            "itemStyle": {"color": "#3b82f6"},
        }],
    }


def _pie_option(labels: list[str], values: list, name: str) -> dict:
    return {
        "tooltip": {"trigger": "item", "formatter": "{a} <br/>{b}: {c} ({d}%)"},
        "legend": {"orient": "vertical", "left": "left"},
        "series": [{
            "name": name,
            "type": "pie",
            "radius": ["40%", "70%"],
            "avoidLabelOverlap": False,
            "itemStyle": {"borderRadius": 4, "borderColor": "#fff", "borderWidth": 2},
            "label": {"show": True, "formatter": "{b}\n{d}%"},
            "data": [{"name": l, "value": v} for l, v in zip(labels, values)],
        }],
    }


def _line_option(x: list[str], series_names: list[str], values: list, value_name: str) -> dict:
    """简化版: 单系列折线"""
    return {
        "tooltip": {"trigger": "axis"},
        "grid": {"left": "3%", "right": "4%", "bottom": "8%", "containLabel": True},
        "xAxis": {"type": "category", "data": x},
        "yAxis": {"type": "value"},
        "series": [{
            "name": value_name,
            "type": "line",
            "data": values,
            "smooth": True,
            "itemStyle": {"color": "#10b981"},
        }],
    }