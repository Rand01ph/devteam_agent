"""MCP tools for time and date operations."""

from typing import Any
from datetime import datetime, date, timedelta


def create_time_tools():
    """Create time-related tools."""
    from claude_agent_sdk import tool

    @tool(
        "get_current_time",
        "Get the current date and time, useful for understanding 'today', 'this week', 'this month', etc.",
        {}
    )
    async def get_current_time(args: dict[str, Any]):
        """Get current date and time information."""
        now = datetime.now()
        today = now.date()

        # Calculate week info
        week_start = today - timedelta(days=today.weekday())  # Monday
        week_end = week_start + timedelta(days=6)  # Sunday

        # Calculate month info
        month_start = today.replace(day=1)
        if today.month == 12:
            next_month = today.replace(year=today.year + 1, month=1, day=1)
        else:
            next_month = today.replace(month=today.month + 1, day=1)
        month_end = next_month - timedelta(days=1)

        # Get week number in month (1-based)
        first_day_of_month = today.replace(day=1)
        week_of_month = (today.day + first_day_of_month.weekday()) // 7 + 1

        # Get ISO week number
        iso_week = today.isocalendar()[1]

        output = f"""**当前时间信息**

- **当前时间**: {now.strftime('%Y-%m-%d %H:%M:%S')}
- **今天**: {today.strftime('%Y-%m-%d')} ({['周一', '周二', '周三', '周四', '周五', '周六', '周日'][today.weekday()]})

**本周**:
- 开始: {week_start.strftime('%Y-%m-%d')} (周一)
- 结束: {week_end.strftime('%Y-%m-%d')} (周日)
- ISO 周数: 第 {iso_week} 周

**本月**:
- {today.year}年{today.month}月
- 开始: {month_start.strftime('%Y-%m-%d')}
- 结束: {month_end.strftime('%Y-%m-%d')}
- 当前是本月第 {week_of_month} 周
"""

        return {
            "content": [{
                "type": "text",
                "text": output
            }]
        }

    @tool(
        "get_date_range",
        "Calculate date range for a specific period like 'last week', 'this month', 'week N of month'",
        {
            "period": str,  # "today", "this_week", "last_week", "this_month", "last_month", "week_N" (N=1,2,3,4,5)
            "year": int,    # Optional: specific year, defaults to current year
            "month": int    # Optional: specific month, defaults to current month
        }
    )
    async def get_date_range(args: dict[str, Any]):
        """Calculate date range for various periods."""
        period = args["period"].lower().strip()
        today = date.today()

        # Get year and month, default to current
        year = args.get("year") or today.year
        month = args.get("month") or today.month

        start_date = None
        end_date = None
        description = ""

        if period == "today":
            start_date = today
            end_date = today
            description = "今天"

        elif period == "yesterday":
            start_date = today - timedelta(days=1)
            end_date = start_date
            description = "昨天"

        elif period == "this_week":
            start_date = today - timedelta(days=today.weekday())
            end_date = start_date + timedelta(days=6)
            description = "本周"

        elif period == "last_week":
            this_week_start = today - timedelta(days=today.weekday())
            start_date = this_week_start - timedelta(days=7)
            end_date = start_date + timedelta(days=6)
            description = "上周"

        elif period == "this_month":
            start_date = date(year, month, 1)
            if month == 12:
                end_date = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = date(year, month + 1, 1) - timedelta(days=1)
            description = f"{year}年{month}月"

        elif period == "last_month":
            if month == 1:
                last_month = 12
                last_year = year - 1
            else:
                last_month = month - 1
                last_year = year
            start_date = date(last_year, last_month, 1)
            end_date = date(year, month, 1) - timedelta(days=1)
            description = f"{last_year}年{last_month}月"

        elif period.startswith("week_"):
            # week_1, week_2, etc. - specific week of the month
            try:
                week_num = int(period.split("_")[1])
                if 1 <= week_num <= 5:
                    # Calculate the start of week N in the given month
                    first_of_month = date(year, month, 1)
                    # Find first Monday of month (or first day if it's Monday)
                    days_until_monday = (7 - first_of_month.weekday()) % 7
                    if first_of_month.weekday() == 0:
                        first_monday = first_of_month
                    else:
                        first_monday = first_of_month + timedelta(days=days_until_monday)

                    # If first day isn't Monday, week 1 starts from day 1
                    if first_of_month.weekday() != 0 and week_num == 1:
                        start_date = first_of_month
                        end_date = first_monday - timedelta(days=1)
                    else:
                        adjusted_week = week_num - 1 if first_of_month.weekday() != 0 else week_num - 1
                        start_date = first_monday + timedelta(weeks=adjusted_week)
                        end_date = start_date + timedelta(days=6)

                    # Clamp to month boundaries
                    if month == 12:
                        month_end = date(year + 1, 1, 1) - timedelta(days=1)
                    else:
                        month_end = date(year, month + 1, 1) - timedelta(days=1)

                    if start_date < first_of_month:
                        start_date = first_of_month
                    if end_date > month_end:
                        end_date = month_end

                    description = f"{year}年{month}月第{week_num}周"
            except (ValueError, IndexError):
                pass

        elif period.startswith("last_") and period[5:].isdigit():
            # last_7 (last 7 days), last_30, etc.
            try:
                days = int(period[5:])
                end_date = today
                start_date = today - timedelta(days=days - 1)
                description = f"最近{days}天"
            except ValueError:
                pass

        if start_date and end_date:
            output = f"""**{description}**

- 开始日期: {start_date.strftime('%Y-%m-%d')}
- 结束日期: {end_date.strftime('%Y-%m-%d')}
- 天数: {(end_date - start_date).days + 1} 天

用于查询时：
- start_date: "{start_date.isoformat()}"
- end_date: "{end_date.isoformat()}"
"""
            return {
                "content": [{
                    "type": "text",
                    "text": output
                }]
            }
        else:
            return {
                "content": [{
                    "type": "text",
                    "text": f"无法解析时间段 '{period}'。支持的格式:\n"
                           "- today, yesterday\n"
                           "- this_week, last_week\n"
                           "- this_month, last_month\n"
                           "- week_1, week_2, week_3, week_4, week_5 (月份中的第N周)\n"
                           "- last_7, last_14, last_30 (最近N天)"
                }]
            }

    @tool(
        "get_week_number",
        "Get the week number for a specific date or find dates for a specific week",
        {
            "date_str": str,  # Optional: ISO date string (YYYY-MM-DD), defaults to today
        }
    )
    async def get_week_number(args: dict[str, Any]):
        """Get week number information for a date."""
        date_str = args.get("date_str")

        if date_str:
            try:
                target_date = date.fromisoformat(date_str)
            except ValueError:
                return {
                    "content": [{
                        "type": "text",
                        "text": f"无效的日期格式: {date_str}。请使用 YYYY-MM-DD 格式。"
                    }]
                }
        else:
            target_date = date.today()

        # Get week of month
        first_day_of_month = target_date.replace(day=1)
        week_of_month = (target_date.day + first_day_of_month.weekday()) // 7 + 1

        # Get ISO week
        iso_year, iso_week, iso_weekday = target_date.isocalendar()

        # Calculate week boundaries
        week_start = target_date - timedelta(days=target_date.weekday())
        week_end = week_start + timedelta(days=6)

        output = f"""**{target_date.strftime('%Y-%m-%d')} 的周信息**

- **月份周数**: {target_date.year}年{target_date.month}月 第{week_of_month}周
- **ISO 周数**: {iso_year}年 第{iso_week}周
- **星期**: {['周一', '周二', '周三', '周四', '周五', '周六', '周日'][target_date.weekday()]}

**该周的日期范围**:
- 开始: {week_start.strftime('%Y-%m-%d')} (周一)
- 结束: {week_end.strftime('%Y-%m-%d')} (周日)

用于周报查询:
- year: {target_date.year}
- month: {target_date.month}
- week_num: {week_of_month}
"""

        return {
            "content": [{
                "type": "text",
                "text": output
            }]
        }

    return [get_current_time, get_date_range, get_week_number]