from setuptools import setup, find_packages
from os import path

this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='jqchat',
    version='0.0.1',
    description="Agent Based Rag&Chat&CodeInterpreter with Interactive UI",
    long_description=long_description,
    long_description_content_type='text/markdown',  # This field specifies the format of the `long_description`.
    packages=find_packages(),
    package_data={'jqchat.webapp': ['static/*', 'static/assets/*']},
    install_requires=[
        'langchain>=0.1.16',
        'openai>=1.2',
        'ipykernel>=6,<7',
        'snakemq>=1,<2',
        'requests>=2,<3',
        'Flask>=3,<4',
        'flask-cors>=4,<5',
        'python-dotenv>=1,<2',
        'pandas>=2,<3',
        'matplotlib>=3,<4',

        
    ],
    entry_points={
        'console_scripts': [
            'jqchat = jqchat.main:main',
        ],
    },
)
