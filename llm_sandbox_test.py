from llm_sandbox import SandboxSession
# Or default image
# with SandboxSession(lang="python", keep_template=True) as session:
#     result = session.run("print('Hello, World!')")
#     print(result)



code = '''
# import plotly.graph_objects as go
# import plotly.express as px
# import seaborn as sns
# import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def calculate_ema(data, alpha):
    ema = []
    ema.append(data[0])  # 初始化第一个值
    for i in range(1, len(data)):
        current_ema = alpha * data[i] + (1 - alpha) * ema[i-1]
        ema.append(current_ema)
    return np.array(ema)

# 生成示例数据（正弦波+噪声）
time = np.linspace(0, 10*np.pi, 100)
base_signal = np.sin(time) * 5
noise = np.random.normal(0, 0.5, time.shape)
raw_data = base_signal + noise

# 计算不同alpha的EMA
ema_alpha_02 = calculate_ema(raw_data, 0.2)
ema_alpha_05 = calculate_ema(raw_data, 0.5)

# 绘制曲线
plt.figure(figsize=(12,6))
plt.plot(time, raw_data, label="原始数据", color="#1f77b4", alpha=0.6)
plt.plot(time, ema_alpha_02, label="EMA (α=0.2)", color="#ff7f0e", linewidth=2)
plt.plot(time, ema_alpha_05, label="EMA (α=0.5)", color="#2ca02c", linestyle="--", linewidth=2)

plt.title("指数移动平均与原始信号对比", fontsize=14)
plt.xlabel("时间单位", fontsize=12)
plt.ylabel("数值幅度", fontsize=12)
plt.legend()
plt.grid(True, linestyle='--', alpha=0.6)
plt.show()
# 保存图像
# output_path = "/data/projects/JqChatV2/workspace/code/ema_comparison.png"
output_path = "ema_comparison.png"
plt.savefig(output_path, bbox_inches='tight')
print(f'<a href="http://10.1.150.105:7861/workspace/download?file={output_path.split("/")[-1]}">下载文件</a>')

'''

with SandboxSession(lang="python", keep_template=True,verbose=True) as session:
    # result = session.run(code,libraries=['numpy','plotly','pandas','matplotlib'])
    result = session.run(code)

    session.copy_from_runtime("ema_comparison.png","/data/projects/JqChatV2/workspace/code/")
    print(result)