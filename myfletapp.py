import flet as ft

md = """
这是一段正常文本

<details open><summary >点击查看"模型思考过程" </summary><font color="grey" size=16px>

**推理步骤1** ： 好的，用户让我绘制sin(x)曲线。首先，我需要确认之前的对话历史里有没有已经处理过这个请求。看历史记录，之前已经有两次提到生成正弦函数sin(x)的曲线图，并且给出了下载链接。不过用户再次提出同样的要求，可能是因为没有收到正确的响应，或者想重新生成。

根据工具列表，应该使用CODE_GENERATION来生成绘图代码，因为这是关于数据可视化的需求。不能直接用python_repl_tool，因为题目要求如果是绘图、图表等应该优先用CODE_GENERATION。

接下来要检查是否需要调用其他工具。这里用户明确说“请绘制sin(x)曲线”，所以不需要搜索网页或查询知识库，直接生成代码即可。需要确保使用CODE_GENERATION工具，并传入正确的查询参数。

然后，按照规范构造JSON。工具名是CODE_GENERATION，参数是query: "请生成Python代码绘制sin(x)曲线"。注意参数必须是字符串，所以需要写成对应的query值。

再确认一下之前的例子，比如用户之前让画图的时候用了CODE_GENERATION。所以这次也应该同样处理。不需要额外的解释，直接输出工具调用的JSON结构。

最后检查格式是否符合要求：不带任何前缀，正确的大括号和引号。避免使用繁体字，全部简体中文。确保参数里的query内容准确。

**推理步骤2** ： 好的，我现在需要处理用户的请求。首先，回顾一下之前的对话历史。用户之前要求“请检索知识库回答，医院信息系统中的基础维护系统完整功能详述 请绘制sin(x)曲线”，但系统在处理过程中发现需要先生成正弦函数的曲线图。

根据之前的交互，助理已经调用了CODE_GENERATION工具来生成绘图代码，然后通过CODE_EXECUTION执行了该代码，并得到了下载链接。现在用户再次发送了执行成功的反馈，要求直接生成最终回答，不再调用其他工具。

我需要确认用户的需求是否满足。用户最初有两个部分：检索知识库关于医院信息系统的基础维护系统功能，以及绘制sin(x)曲线。不过，在之前的回复中，系统已经尝试过检索知识库但未能找到完整信息，所以可能主要需求是绘制图表。而助理已经完成了绘图任务，并提供了下载链接。

现在需要确保最终回答只包含下载链接，不需要额外内容。检查之前的例子，当执行成功后，回复的是一个包含下载链接的HTML链接。因此，正确的做法是直接输出这个链接作为最终答案。

同时要注意不要添加任何其他解释或工具调用，严格按照用户指示“不再调用任何工具”。所以只需要把生成的链接返回即可。</font></details>

------


<a href='http://10.1.150.105:7861/workspace/download?file=sin_curve.png'>下载 sin(x) 曲线图</a>

------
<font color="red">内容由AI生成</font>

------
"""


md1 = """
\n```python\nimport matplotlib.pyplot as plt\n\nimport plotly.graph_objects as go\nimport plotly.express as px\nimport numpy as np\nimport seaborn as sns\nimport pandas as pd\n\n# 设置中文字体和负号显示\nplt.rcParams[\'font.sans-serif\'] = [\'SimHei\']\nplt.rcParams[\'axes.unicode_minus\'] = False\n\n# 生成数据点\nx = np.linspace(0, 2 * np.pi, 100)\ny = np.sin(x)\n\n# 创建图表\nplt.figure(figsize=(10, 6))\nplt.plot(x, y, \'b-\', linewidth=2)\nplt.title(\'正弦函数 sin(x) 曲线\')\nplt.xlabel(\'x\')\nplt.ylabel(\'sin(x)\')\nplt.grid(True, linestyle=\'--\', alpha=0.7)\n\n# 保存图像到指定路径\noutput_path = \'/data/projects/JqChatV2/workspace/code/sin_curve.png\'\nplt.savefig(output_path)\nplt.close()\n\n# 输出下载链接\nprint("<a href=\'http://10.1.150.105:7861/workspace/download?file=sin_curve.png\'>下载 sin(x) 曲线图</a>")\n```\n\n', '', '<details open>\n<summary>点击查看"模型思考过程" </summary>\n<font color="grey" size=16px>\n\n**推理步骤1** ： 好的，用户让我绘制sin(x)曲线。首先，我需要确认之前的对话历史里有没有已经处理过这个请求。看历史记录，之前已经有两次提到生成正弦函数sin(x)的曲线图，并且给出了下载链接。不过用户再次提出同样的要求，可能是因为没有收到正确的响应，或者想重新生成。\n\n根据工具列表，应该使用CODE_GENERATION来生成绘图代码，因为这是关于数据可视化的需求。不能直接用python_repl_tool，因为题目要求如果是绘图、图表等应该优先用CODE_GENERATION。\n\n接下来要检查是否需要调用其他工具。这里用户明确说“请绘制sin(x)曲线”，所以不需要搜索网页或查询知识库，直接生成代码即可。需要确保使用CODE_GENERATION工具，并传入正确的查询参数。\n\n然后，按照规范构造JSON。工具名是CODE_GENERATION，参数是query: "请生成Python代码绘制sin(x)曲线"。注意参数必须是字符串，所以需要写成对应的query值。\n\n再确认一下之前的例子，比如用户之前让画图的时候用了CODE_GENERATION。所以这次也应该同样处理。不需要额外的解释，直接输出工具调用的JSON结构。\n\n最后检查格式是否符合要求：不带任何前缀，正确的大括号和引号。避免使用繁体字，全部简体中文。确保参数里的query内容准确。\n\n**推理步骤2** ： 好的，我现在需要处理用户的请求。首先，回顾一下之前的对话历史。用户之前要求“请检索知识库回答，医院信息系统中的基础维护系统完整功能详述 请绘制sin(x)曲线”，但系统在处理过程中发现需要先生成正弦函数的曲线图。\n\n根据之前的交互，助理已经调用了CODE_GENERATION工具来生成绘图代码，然后通过CODE_EXECUTION执行了该代码，并得到了下载链接。现在用户再次发送了执行成功的反馈，要求直接生成最终回答，不再调用其他工具。\n\n我需要确认用户的需求是否满足。用户最初有两个部分：检索知识库关于医院信息系统的基础维护系统功能，以及绘制sin(x)曲线。不过，在之前的回复中，系统已经尝试过检索知识库但未能找到完整信息，所以可能主要需求是绘制图表。而助理已经完成了绘图任务，并提供了下载链接。\n\n现在需要确保最终回答只包含下载链接，不需要额外内容。检查之前的例子，当执行成功后，回复的是一个包含下载链接的HTML链接。因此，正确的做法是直接输出这个链接作为最终答案。\n\n同时要注意不要添加任何其他解释或工具调用，严格按照用户指示“不再调用任何工具”。所以只需要把生成的链接返回即可。\n\n</font></details>\n\n------\n\n\n<a href=\'http://10.1.150.105:7861/workspace/download?file=sin_curve.png\'>下载 sin(x) 曲线图</a>\n\n------\n<font color="red">内容由AI生成</font>\n\n------\n'

"""
def main(page: ft.Page):
    page.scroll = ft.ScrollMode.AUTO
    page.add(
        ft.Markdown(
            md,
            selectable=True,
            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
            on_tap_link=lambda e: page.launch_url(e.data),
            code_theme = ft.MarkdownCodeTheme.GITHUB,
            shrink_wrap=True,
            md_style_sheet = ft.MarkdownStyleSheet()
        )
    )


ft.app(main,port=8090)