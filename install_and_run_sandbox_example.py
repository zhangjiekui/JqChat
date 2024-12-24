# https://github.com/lyric-project/lyric

# Install:
    # pip install "lyric-py>=0.1.5" 
    # pip install "lyric-py-worker>=0.1.5"
    # pip install "lyric-js-worker>=0.1.5"
    # pip install "lyric-component-ts-transpiling>=0.1.5"
# Install All:
# pip install "lyric-py>=0.1.5" "lyric-py-worker>=0.1.5" "lyric-js-worker>=0.1.5" "lyric-component-ts-transpiling>=0.1.5"


import asyncio
import json
from lyric import DefaultLyricDriver

python_code = """
try:
    import pandas
except:
    import subprocess
    subprocess.call(["pip", "install", "pandas"])
    print("安装成功pandas")
    import pandas
    print("导入成功pandas")

def add(a, b):
    return a + b
result = add(1, 2)
print(result)
"""


python_code_as_func = """
def add_wrap(message_dict={'a':111,'b':2}):
    a = message_dict.get("a",0)
    b = message_dict.get("b",0)
    return a + b
"""

js_code = """
console.log('Hello from JavaScript!');
"""

async def main():
    # lcd = DefaultLyricDriver(host="127.0.0.1", log_level="ERROR")
    lcd = DefaultLyricDriver()
    lcd.start()

    # Load workers(default: Python, JavaScript)
    await lcd.lyric.load_default_workers()

    # Execute Python code
    py_res = await lcd.exec(python_code, "python")
    print(py_res)


    # Execute Python Function
    input_data = {
    "a": "10",
    "b": "20",
}
    input_bytes = json.dumps(input_data).encode("utf-8")

    py_res = await lcd.exec1(python_code_as_func, input_bytes, "add_wrap", lang="python")
    print(py_res)

    # Execute JavaScript code
    js_res = await lcd.exec(js_code, "javascript")
    print(js_res)

    # Stop the driver
    lcd.stop()

if __name__ == "__main__":
    asyncio.run(main())