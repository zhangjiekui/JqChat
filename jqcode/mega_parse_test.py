from megaparse.Converter import MegaParse

files = ['/data/projects/JqChat/test_en.pdf','/data/projects/JqChat/test_zh.pdf','/data/projects/JqChat/book.pdf']
for file in files:
    md_file = file.replace('pdf','md')
    megaparse = MegaParse(file_path=file)
    content = megaparse.convert()
    print(f'{file} converted')
    megaparse.save_md(content, md_file)
    print(f'{md_file} saved')

