import plotly.graph_objects as go
import plotly.express as px
import seaborn as sns
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
# 生成x值，从0到2*pi
x = np.linspace(0, 2 * np.pi, 400)
# 计算sin(x)
y = np.sin(x)
# 创建图表
plt.figure(figsize=(10, 5))
plt.plot(x, y, label='sin(x)')
plt.title('Sin(x) Curve')
plt.xlabel('x')
plt.ylabel('sin(x)')
plt.legend()
plt.grid(True)
# 保存图表
plt.savefig('/data/projects/JqChatV2/JqChat/workspace/sin_curve.png')
plt.show()
# 打印下载链接
print('<a href="/download?file=sin_curve.png">下载文件</a>"')