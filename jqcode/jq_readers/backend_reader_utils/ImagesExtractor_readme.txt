解决pdf2docx valueerror: unsupported colorspace for '{output}'错误
对/root/.virtualenvs/test/lib/python3.10/site-packages/pdf2docx/image/ImagesExtractor.py
做了更改

        # 做了更改
        if not image.colorspace.name in (fitz.csGRAY.name, fitz.csRGB.name):
            image = fitz.Pixmap(fitz.csRGB, image)