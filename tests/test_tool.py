import os
from pathlib import Path
import sys
# sys.path.append(Path(__file__).absolute().parent.parent )
# print(Path(__file__).absolute().parent.parent)
# os.chdir(Path(__file__).absolute().parent.parent)
from jqcode.jq_code_executor.code_executor import CodeExecutorTool



def test_code_executor():
    tool = CodeExecutorTool()
    result=tool.call(code=
        """
x = [1,5]\n
y = [1,5]\n
plt.plot(x,y)\n 
plt.show()
        """)