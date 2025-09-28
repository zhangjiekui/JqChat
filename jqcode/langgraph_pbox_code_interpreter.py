# https://github.com/pydaxing/PandoraBox

# /data/projects/JqChatV2/JqChat/langgraph_pbox_code_interpreter.py
# /data/projects/JqChatV2/JqChat/jqcode/langgraph_in_class.py
from pbox import CodeSandBox

code_sandbox = CodeSandBox()
result = code_sandbox.execute_code("print('Hello, PandaroBox!')")

print(str(result))
print(result.logs.stdout)


from pbox import CodeSandBoxManager

csb_manager = CodeSandBoxManager()

pbox_api_key = 'pb-xMODnU404A99DBc97E7C42568987f226a66EB2F5NoTVQSpa'
# creqte sandbox
kernel_id = csb_manager.create_sandbox(pbox_api_key)

# list sandbox
sbs = csb_manager.get_sandbox(pbox_api_key)

# execute code
code = '''
import plotly.graph_objects as go
import plotly.express as px
import seaborn as sns
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

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

# 保存图像
output_path = "/data/projects/JqChatV2/workspace/code/ema_comparison.png"
plt.savefig(output_path, bbox_inches='tight')
plt.savefig(output_path+"1", bbox_inches='tight')
print(f'图像已保存到 {output_path}')
print(f'图像已保存到 {output_path}+"1"')
# print(f'<a href="http://10.1.150.105:7861/workspace/download?file={output_path.split("/")[-1]}">下载文件</a>')

'''
result = csb_manager.execute_code (
    pbox_api_key,
    kernel_id,
    code=code
)

print(result)

# # close sandbox, If you forget, it will automatically close after 6 hours.
# csb_manager.close_sandbox(
#     "your-api-key",
#     "your-kernel-id"
# )


from pbox import CodeSandBox

code_sandbox = CodeSandBox()
code_sandbox.execute_code("x = 'Hello, PandoraBox!'")
result = code_sandbox.execute_code(code)

print(str(result))
print(result.logs.stdout)