def calculate_tax(income: float) -> float:
    """
    根据提供的收入计算中国的个人所得税。

    参数:
        income (float): 个人的总收入。

    返回:
        float: 计算出的税额。
    """
    # 中国个人所得税的税率区间，根据最新的税率表。
    brackets = [
        (0, 36000, 0.03),
        (36000, 144000, 0.1),
        (144000, 300000, 0.2),
        (300000, 420000, 0.25),
        (420000, 660000, 0.3),
        (660000, 960000, 0.35),
        (960000, float('inf'), 0.45)
    ]

    tax = 0
    for i, (lower, upper, rate) in enumerate(brackets):
        if income > upper:
            tax += (upper - lower) * rate
        elif income > lower:
            tax += (income - lower) * rate
            break

    return tax

if __name__ == "__main__":
    # 示例用法: 计算收入为500000 CNY的税额
    income = 500000
    tax = calculate_tax(income)
    print(f"收入为 {income} CNY 的税额是 {tax:.2f} CNY。")
