import os

def list_files(startpath):
    file_list = []
    for root, dirs, files in os.walk(startpath):
        # if root in '__pycache__':
        dir_name = root.split(os.path.sep)[-1]
        # if 'pycache' in root:
        #     print(root)
        if not dir_name.startswith(tuple(['.', '_'])):
            level = root.replace(startpath, '').count(os.sep)
            indent = ' ' * 4 * (level)
            print('{}{}/'.format(indent, os.path.basename(root)))
            subindent = ' ' * 4 * (level + 1)
            for f in files:
                if not f.startswith(tuple(['~', '_'])) and \
                not f.endswith(tuple(['.tmp', '.bak'])) and \
                f.endswith(tuple(['.docx', '.pdf', '.txt','.py'])):
                    print('{}{}'.format(subindent, f))
                    file_list.append(os.path.join(root, f))
    return file_list

# 使用方法：
if __name__ == "__main__":
    code_dir = '/home/jqsoft/AgentRagChatCI/AgentRagChatCI-0.0.1/jqcode'
    file_list = list_files(code_dir)
    # 方法内已有打印输出，不需要再打印
    # for file in file_list:
    #     print(file)