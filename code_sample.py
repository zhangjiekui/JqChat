import numpy as np
import matplotlib.pyplot as plt

# 生成样本数据
np.random.seed(0)  # 确保每次运行结果相同
num_points = 100  # 数据点数
t = np.arange(num_points)
data_with_trend = 5 + 0.05 * t + 15 * np.sin(t / 4)
noise = np.random.normal(0, 2, num_points)
data = data_with_trend + noise
def exponential_moving_average(data, span):
    """
    计算指数滑动平均
    :param data: 原始数据序列
    :param span: 指数滑动平均的时间跨度
    :return: 滑动平均后的数据
    """
    ema = data.copy()
    for i in range(1, len(data)):
        ema[i] = ema[i-1] + (2/(1+span)) * (data[i] - ema[i-1])
    return ema
# 设置EMA参数
span = 10  # EMA的周期

# 计算EMA
ema_data = exponential_moving_average(data, span)

# 绘制图表
plt.figure(figsize=(10, 5))
plt.plot(t, data, label='Original Data', alpha=0.7)
plt.plot(t, ema_data, label='EMA', color='orange')
plt.title('Exponential Moving Average')
plt.xlabel('Index')
plt.ylabel('Value')
plt.legend()
plt.show()
plt.savefig('tem.png')
