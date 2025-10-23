import os
import io
import uuid
import base64
import PIL.Image
from agent_sandbox import Sandbox
from jqcode.jq_utils.jq_watermark_func_and_result.crypto_watermark_image import ImageWatermark
from jqcode.jq_utils.logger import jqkj_logger
logger = jqkj_logger(__file__).get_logger()

class AioSandbox:
    def __init__(self, base_url="http://10.1.150.105:7080",user_request_url:str=None):
        self.client = Sandbox(base_url=base_url)
        self.home_dir = self.client.sandbox.get_sandbox_context().home_dir
        self.wm = ImageWatermark("strong_password_123")
        self.work_dir: str = os.getenv('workspace')
        self.instance_id: str = str(uuid.uuid4())
        if user_request_url:
            valid_url = user_request_url
        else:
            valid_url = os.getenv("deployment_url",'http://10.1.150.105:7861/workspace')
        self.user_request_url = valid_url
        logger.warning(f"ImageWatermark初始化成功。")
        logger.warning(f"Sandbox初始化成功。'home dir': {self.home_dir} , 'url': {base_url}")
        logger.warning(f"ImageWatermark初始化成功。")
    def get_file_path(self, file_path_name:str=f".bashrc"):
        if os.path.exists(file_path_name):
            return file_path_name
        else:
            new_file_path_name = os.path.join(self.home_dir, file_path_name)
            if os.path.exists(new_file_path_name):
                return new_file_path_name
            else:
                logger.warning(f"{file_path_name} or {new_file_path_name} not found")
                # raise FileNotFoundError(f"{file_path_name} or {new_file_path_name} not found")
    def _serve_image(self, image_base64: str, target_width = 800, target_type ='PNG') -> str:
        image_file = f'{uuid.uuid4()}.png'
        local_image_file = os.path.join(self.work_dir,"code", image_file)
        png_bytes = base64.b64decode(image_base64)
        bytes_io = io.BytesIO(png_bytes)
        image = PIL.Image.open(bytes_io)        
        # 根据指定的目标宽度，计算等比缩放后的高度
        original_width, original_height = image.size
        aspect_ratio = original_height / original_width
        target_height = int(target_width * aspect_ratio)
        # 调整图像大小（使用高质量的 LANCZOS 重采样）
        resized_image = image.resize((target_width, target_height), PIL.Image.Resampling.LANCZOS)

        # 保存为 PNG
        resized_image.save(local_image_file, target_type)
        # 水印、元数据
        result = self.wm.encrypt_and_or_decrypt_img(local_image_file)

        logger.warning(f"CodeExecutorTool _serve_image(): local_image_file={local_image_file}")
        if "/workspace" not in self.user_request_url:
            deployment_url = f'{self.user_request_url}/workspace'
        else:
            deployment_url = self.user_request_url
        image_server_url = os.path.join(deployment_url,"images")
        logger.warning(f"CodeExecutorTool _serve_image(): deployment_url={deployment_url}")
        if image_server_url:
            return f'{image_server_url}/{image_file}'
        return local_image_file    
    # File operations
    def read_file_content(self, file_path_name=f".bashrc"):
        try:
            file_path_name = self.get_file_path(file_path_name)
            result = self.client.file.read_file(file=file_path_name)
            return result.data.output
        except Exception as e:
            msg = (f"Error: {e}")
            print(msg)
            return msg

    # Execute shell commands
    def exec_shell_command(self, command: str="ls -la"):
        result = self.client.shell.exec_command(command=command)
        return result.data.output
    
    def call(self, code:str="print('hello world!')", lang="python"):
        return self.exec_python_or_js_code(code = code, lang = lang)
    # run code in the sandbox
    def exec_python_or_js_code(self, code:str="print('hello world!')", lang="python"):
        status = False
        text = ""
        image = ""
        error_traceback_msg = ""
        if lang == "python":
            run_result = self.client.jupyter.execute_jupyter_code(code=code)            
        else:
            run_result = self.client.nodejs.execute_nodejs_code(code=code)
        
        
        data_result = run_result.data
        status = run_result.success 

        if status:
            image_idx = 0
            for output in data_result.outputs:
                if output.output_type == "display_data":
                    if output.data.get("image/png"):
                        image_idx += 1
                        image_b64 = output.data.get("image/png")
                        image_url = self._serve_image(image_b64)
                        image += '![fig-%03d](%s)' % (image_idx, image_url) + "\n"

                if output.output_type == "stream" and output.name == "stdout":
                    if output.text:
                        text += output.text + "\n"
            # needed_result = {"status":status,"text":text, "image":image, "code":code}
            needed_result = [{"result":{"text":text, "image":image}},status]
            return needed_result
        else:
            for output in data_result.outputs:
                if output.output_type == "error":
                    error_msg = f"{output.ename}: {output.evalue}. Traceback details:\n"
                    traceback_msg = "\n".join(output.traceback)
                    error_traceback_msg = error_msg + traceback_msg
            print(error_traceback_msg)
            needed_result = needed_result = [error_traceback_msg,status]
            return needed_result
    
if __name__ == "__main__":
    sandbox = AioSandbox()
    print(sandbox.exec_python_or_js_code())
    # print(sandbox.read_file_content())
    # print(sandbox.exec_shell_command())
    print("============================================================================")
    py_code = """
    import matplotlib.pyplot as plt
    import plotly.graph_objects as go
    import plotly.express as px
    import numpy as np
    import seaborn as sns
    import pandas as pd

    # 设置中文字体和负号显示
    plt.rcParams['font.sans-serif'] = ['SimHei']  # 使用黑体显示中文
    plt.rcParams['axes.unicode_minus'] = False    # 显示负号

    # 生成数据
    x = np.linspace(0, 2 * np.pi, 1000)  # 从0到2π，生成1000个点
    y = np.sin(x)

    # 创建图像
    plt.figure(figsize=(8, 5))  # 设置画布大小
    plt.plot(x, y, label='sin(x)', color='blue', linewidth=2)

    # 添加标注
    plt.title('Sine Function Curve')
    plt.xlabel('x (radians)')
    plt.ylabel('sin(x)')
    plt.grid(True)
    plt.axhline(0, color='black', linewidth=0.5)
    plt.axvline(0, color='black', linewidth=0.5)
    plt.legend()

    # 显示图像
    plt.show()
    """

    result_list = sandbox.exec_python_or_js_code(code=py_code, lang="python")
    result = result_list[0].get("result",None)
    status = result_list[1]
    if status:        
        text = result.get("text",None)
        image = result.get("image",None)
        print(f"{text=}")
        print(f"{image[0:100]=}")
    else:
        error_traceback_msg = result.get("error_traceback_msg",None)
        print(error_traceback_msg)
    # docker run -it -p 8080:8080 --name aiosandbox enterprise-public-cn-beijing.cr.volces.com/vefaas-public/all-in-one-sandbox:1.0.0.125


# 修改镜像，安装Python包
    # docker run -it --rm --entrypoint /bin/bash enterprise-public-cn-beijing.cr.volces.com/vefaas-public/all-in-one-sandbox:1.0.0.125
    # /opt/python3.12/bin/pip list
    # /opt/python3.12/bin/pip install plotly seaborn

# 保存和运行镜像[测试]
    # docker commit 67202306d56e aio_sandbox_jq:v1.0
    # ！！！需映射/data/projects/JqChatV2/workspace到容器中
    # docker run -it -p 7080:8080 -v /data/projects/JqChatV2/workspace:/data/projects/JqChatV2/workspace --name jqsandbox  aio_sandbox_jq:v1.0
    # sh /opt/gem/run.sh

# 正式运行镜像
"""
docker run -d \
  -p 7080:8080 \
  -v /data/projects/JqChatV2/workspace:/data/projects/JqChatV2/workspace \
  --name jqsandbox \
  aio_sandbox_jq:v1.0 \
  sh /opt/gem/run.sh
"""

"""
Github:    https://github.com/agent-infra/sandbox

📖 Documentation: http://10.1.150.105:7080/v1/docs
🌐 VNC Browser:   http://10.1.150.105:7080/vnc/index.html?autoconnect=true
💻 VSCode Server: http://10.1.150.105:7080/code-server/
🤖 MCP Services:  http://10.1.150.105:7080/mcp

"""





