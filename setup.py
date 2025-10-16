from setuptools import setup, find_namespace_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

with open("VERSION", "r") as fh:
    version = fh.read().strip()

setup(
    name='cltl.llm',
    version=version,
    package_dir={'': 'src'},
    packages=find_namespace_packages(include=['cltl.*', 'cltl_service.*'], where='src'),
    data_files=[('VERSION', ['VERSION'])],
    url="https://github.com/leolani/cltl-llm",
    license='MIT License',
    author='CLTL',
    author_email='piek.vossen@vu.nl',
    description='LLM component for Leolani',
    long_description=long_description,
    long_description_content_type="text/markdown",
    python_requires='>=3.10',
    install_requires=['cltl.combot', 'emissor', 'openai', 'ollama', 'langchain.ollama'],
    extras_require={
        "service": [
            "cltl.emissor-data",
        ]}
)
